# Plan: Floating IP Allocation and VM Start Command Reorder (plan-start2.md)

*Updated 3 days ago by Gregor von Laszewski*

---

## Overview

This document captures the discussion and proposed workflow for handling **floating IPs** (FIPs) and the **VM start command** in a more reliable, race‑condition‑aware manner.  It is intended as a concrete plan that can be turned into code (e.g. in the `cloudmesh-ai-vm` CLI) and as an internal reference for developers working on the Jetstream2 and Chameleon providers.

---

## Key Points from the Conversation

1. **Reuse Existing Unused Floating IPs**
   - Do **not** allocate a new floating IP if an unassigned one already exists in the project quota. Reuse first.
2. **Pre‑Flight Floating IP Claim**
   - Attempt to claim a floating IP **before** issuing the VM boot command unless the `--noip` flag is set.
   - If the claim fails after a configurable number of retries, abort the VM creation early to avoid orphaned instances.
3. **Graceful Exit on Scarcity**
   - When no floating IP can be obtained (exhausted pool, quota limits, or persistent race‑condition failures), exit with a clear error message and a non‑zero status code.
4. **Rollback on VM Creation Failure**
   - If the VM fails to start after a floating IP has been claimed, release or unlock the IP to avoid leaking resources.
5. **`--noip` Flag**
   - Some VMs do not require a public floating IP. The `--noip` flag skips all floating‑IP‑related logic.

---

## Technical Strategy & Core Principles

1. **Floating IP Reuse First** – Search for unassigned existing FIPs within the project quota before attempting to allocate a new public IP from the external network.
2. **Pre‑Flight Claiming Guard** – Claim/allocate the floating IP **before** issuing the VM boot command (unless `--noip` is set). If no IP is available after retries, fail fast without spinning up an idle instance.
3. **Atomic Race‑Condition Handling** – Use retries with exponential back‑off and jitter during IP allocation to handle concurrent execution across different project users.
4. **Clean Rollback & Teardown** – If VM creation fails post‑IP acquisition, safely retain or release the floating IP back to the pool based on execution flags.

---

## Dynamic Execution Flow

```
[Start VM Provision Request]
   |
   +-- Is `--noip` set? ────> [Boot VM directly without FIP] → DONE
   |
   +-- NO → [Pre‑Flight FIP Strategy]
          │
          ├─ 1. Query existing unattached project FIPs
          ├─ 2. Attempt attachment reservation lock
          └─ 3. If none available, request NEW allocation with exponential backoff/retries
                |
                +-- Allocation Failed after N retries? → [Graceful Exit / Error Logged]
                |
                +-- SUCCESS → [Boot VM Instance]
                      |
                      +-- Boot Failed? → [Rollback: Release/Unlock FIP] → EXIT WITH FAILURE
                      |
                      +-- SUCCESS → [Associate FIP to Server Interface] → DONE
```

---

## Phased Workflow Steps

### Phase 1 – Flag Processing & Pre‑Flight Capacity Checks

1. **Evaluate Constraints (`--noip` Flag)**
   - If present, skip all floating IP allocation logic and proceed directly to the standard `openstack server create` (or equivalent) call.
2. **Project Floating IP Fleet Scan**
   - Query OpenStack Neutron for active project floating IPs where `port_id IS NULL` or `status == 'DOWN'`.
   - Return a prioritized list of **Unassigned Existing FIPs**.

### Phase 2 – Floating IP Reservation & Allocation Loop

1. **Attempt Unassigned FIP Claim** – Iterate over the list of unassigned project FIPs:
   - Attempt an immediate temporary tag/lock or state reservation on the target FIP ID to signal usage to parallel workflow threads.
   - If locked successfully, pass this FIP ID to the boot phase.
2. **Allocate‑New Loop with Retry/Backoff** – If no unassigned FIP is available:
   - Enter a deterministic retry loop (e.g. `N = 3‑5` attempts, initial delay = 2 s, max back‑off = 15 s + random jitter).
   - Issue a request to create a new floating IP from the public external pool (`ext‑net` / `public`).
   - Catch pool‑exhaustion errors (`503 Service Unavailable`, `404 Pool Exhausted`, or quota over‑limit exceptions).
3. **Graceful Pre‑Flight Exit** – If all retry attempts fail:
   - Print a clear error message (e.g. `Error: Floating IP scarcity detected. No IP available. Provisioning aborted pre‑flight.`).
   - **Do not** start the VM. Exit with a non‑zero status code.

### Phase 3 – Instance Provisioning & IP Binding

1. **Trigger Instance Creation** – Call the appropriate API (`openstack server create` or the Python SDK equivalent) and monitor the build state until it reaches `ACTIVE`.
2. **Associate Secured FIP to Server** – Bind the obtained floating IP address to the primary port / fixed private IP of the newly provisioned server and verify attachment.
3. **Rollback Safeguard** – If server creation fails or times out (`ERROR` state):
   - Disassociate/unlock the claimed floating IP.
   - Log telemetry and exit cleanly.

---

## Pseudo‑Algorithm (CLI / SDK Pipeline)

```python
def create_vm_with_fip_guard(vm_name, image, flavor, network, noip=False, retries=4):
    """Provision a VM with pre‑flight Floating IP handling.

    Parameters
    ----------
    vm_name: str
        Desired name of the VM.
    image: str
        Image identifier.
    flavor: str
        Flavor identifier.
    network: str
        Network identifier to attach the VM to.
    noip: bool, optional
        If True, skip any floating IP allocation.
    retries: int, optional
        Number of allocation attempts when requesting a new FIP.
    """
    if noip:
        print(f"--> Provisioning {vm_name} without Floating IP (--noip set)...")
        return boot_vm(vm_name, image, flavor, network)

    fip = None

    # Phase 1: Try reusing existing unattached FIPs
    unassigned_fips = list_unassigned_project_fips()
    if unassigned_fips:
        fip = lock_and_select_fip(unassigned_fips)

    # Phase 2: Allocate a new FIP if needed, with exponential back‑off
    if not fip:
        for attempt in range(1, retries + 1):
            try:
                print(f"--> Attempting FIP allocation (Attempt {attempt}/{retries})...")
                fip = allocate_new_floating_ip()
                if fip:
                    break
            except IPPoolExhaustedError:
                # Exponential back‑off with jitter
                time.sleep(2 ** attempt + random.uniform(0, 1))

    # Phase 3: Abort if we still have no FIP
    if not fip:
        print("❌ ERROR: Cannot secure a Floating IP due to cloud pool scarcity.")
        print("❌ Aborting VM creation to prevent unroutable instances.")
        sys.exit(1)

    # Phase 4: Boot VM and attach the FIP
    try:
        vm = boot_vm(vm_name, image, flavor, network)
        attach_floating_ip(vm.id, fip.id)
        print(f"✅ Success: Server {vm_name} running at {fip.ip_address}")
        return vm
    except Exception as e:
        print(f"❌ Boot failed: {e}. Releasing/unlocking FIP {fip.ip_address}...")
        release_or_unlock_fip(fip.id)
        sys.exit(1)
```

---

## Recommendations & Next Steps

* **Add a `--noip` CLI flag** to the existing `cmx vm start` command (if not already present).
* **Implement helper functions** referenced in the pseudo‑algorithm:
  - `list_unassigned_project_fips`
  - `lock_and_select_fip`
  - `allocate_new_floating_ip`
  - `boot_vm`
  - `attach_floating_ip`
  - `release_or_unlock_fip`
* **Introduce exponential back‑off logic** using standard libraries (`time`, `random`).
* **Write unit tests** for each phase, especially the retry‑and‑rollback behavior.  Place tests under `tests/unit/` following the existing naming conventions (e.g., `test_fip_allocation.py`).
* **Update the documentation** (`docs/providers/openstack/jetstream.md` and `docs/providers/openstack/chameleon.md`) to describe the new workflow and the `--noip` flag.

---

*This plan should be reviewed by the core development team and incorporated into the next sprint.*
