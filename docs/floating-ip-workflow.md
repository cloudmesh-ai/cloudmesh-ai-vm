ou # Floating IP Workflow

This document describes the **floating IP (FIP) workflow** that is used when a
VM is started via the `cmx vm start` command.  The workflow is currently
implemented for OpenStack‑based providers (Jetstream, Chameleon, generic
OpenStack) and follows the design outlined in `plan-start2.md`.

---

## 1. Determine if an IP is required

* The CLI parses the `--noip` flag.  If the flag is present, the `assign_ip`
  argument is set to ``False`` and the provider skips any IP handling.
* If `--noip` is **not** supplied, `assign_ip` defaults to ``True`` (or to the
  value of the legacy `--ip` flag when that is used).

## 2. Pre‑flight: reuse an existing unassigned floating IP

* The provider calls :func:`cloudmesh.ai.vm.fip_utils.list_unassigned_fips`
  to retrieve all floating IPs in the project that have no attached ``port_id``.
* If any unassigned IPs are returned, the first one is selected via
  :func:`cloudmesh.ai.vm.fip_utils.lock_and_select_fip`.  A real implementation
  would add a temporary tag or metadata to lock the IP and avoid race
  conditions.

## 3. Allocation fallback – create a new floating IP

* When no unassigned IPs exist, the provider attempts to allocate a new one with
  :func:`cloudmesh.ai.vm.fip_utils.allocate_fip_with_retry`.
 * This helper retries the allocation up to **4** times, using exponential
   back‑off (2 s, 4 s, 8 s, …) and a small jitter to reduce contention.
 * When a new floating IP is allocated, the provider sets its ``description``
   field to the Cloudmesh username (or a generic placeholder). This makes it
   easier to identify which user owns the IP in the OpenStack dashboard and
   for billing purposes.

## 4. VM creation

* With a floating IP (or ``None`` when `--noip` is used) the provider creates the
  server via the OpenStack SDK and waits for the instance to reach the **ACTIVE**
  state.

## 5. Attach the floating IP

* After the VM is ACTIVE, the reserved IP address is attached to the instance
  using ``conn.compute.add_floating_ip_to_server``.
* The CLI then verifies SSH connectivity (via the existing `wait_for_login`
  helper) and reports success or a timeout warning.

## 6. Roll‑back on failure

* If any step after the IP reservation fails (e.g., VM creation, waiting for
  ACTIVE, or attaching the IP), the provider performs a cleanup:
  * The reserved floating IP is released with :func:`cloudmesh.ai.vm.fip_utils.release_fip`.
  * If the VM was already created, it is deleted to avoid orphaned resources.

---

The `--noip` flag overrides this entire process, allowing you to start a VM
without consuming a public IP address.  This is particularly useful when IP
resources are scarce or when you only need internal network connectivity.

For the full design discussion and pseudo‑algorithm, see
[`plan-start2.md`](plan-start2.md).
