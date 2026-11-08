# cmx vm purge

## Overview

`cmx vm purge` is a high‑level clean‑up command that deletes **all** virtual machines, releases **all** floating IPs, and removes **all** reservations for a given cloud (or for every enabled cloud when no cloud is specified).  This is intended for quickly resetting a cloud after a test run, teaching session, or any situation where a fresh environment is needed.

The command prompts for confirmation to avoid accidental data loss.  For automated scripts the prompt can be bypassed using `--yes` (or `-y`).

## Usage

```bash
cmx vm purge [--cloud=CLOUD] [--yes | -y]
```

* `--cloud TEXT` – Target a specific enabled cloud. If omitted, all enabled clouds are purged.
* `--yes`, `-y` – Skip the interactive confirmation prompt (useful for CI/CD pipelines).

## Behaviour

1. **Safety Prompt** – Unless `--yes`/`-y` is supplied, the command asks:
   ```
   Are you sure you want to purge all resources for cloud <cloud_name>? [y/N]:
   ```
2. **VM Deletion** – Iterates over each VM returned by the provider and calls `provider.delete(name)`.
3. **Floating IP Release** – If the provider implements `list_floating_ips()` and `release_floating_ip_by_ip(address)`, those are used.  Otherwise it falls back to the existing `release_floating_ip(name)`.
4. **Reservation Removal** – If the provider implements `list_reservations()` and `delete_reservation(res_id)`, those are called (e.g., Chameleon uses `chi.lease.delete_lease`).
5. **Logging** – Each action is logged via the shared console object. Errors are reported but the command continues processing remaining items.
6. **Idempotence** – Running the command again after a successful purge results in “nothing to delete” messages rather than errors.

## Examples

```bash
cmx vm purge                     # Interactive prompt, all clouds
cmx vm purge --cloud chameleon   # Interactive, only Chameleon
cmx vm purge -y                  # Non‑interactive, all clouds
cmx vm purge --cloud multipass -y
```

## Testing (recommended)

Unit tests should mock the provider APIs to verify:

* The confirmation prompt is displayed and can be bypassed with `--yes`.
* `delete`, `release_floating_ip_by_ip`, and `delete_reservation` are called for each resource.
* Errors are logged but do not abort the purge.
