# cmx vm status

## Overview

The `cmx vm status` command provides a concise audit of the resources currently allocated in a cloud provider (or across all enabled clouds). It lists:

1. **Running VMs** – name, status, IP address, image, flavor, etc.
2. **Floating IPs** – address, attached VM (if any), and status.
3. **Reservations / Leases** – reservation ID, type, status, start time, and end time.

The output is a human‑readable table divided into the three sections above.  An optional `--json` flag produces the same information as a JSON document, suitable for scripting.

## Usage

```bash
cmx vm status [--cloud=CLOUD] [--json]
```

* `--cloud TEXT` – Limit the audit to a specific enabled cloud. If omitted, all enabled clouds are included.
* `--json` – Emit the information as a JSON document instead of a table.

## Examples

```bash
cmx vm status                     # All clouds, human‑readable table
cmx vm status --cloud openstack   # Only OpenStack cloud
cmx vm status --json              # JSON output for all clouds
```

## JSON Format

When `--json` is used, the output is structured per cloud:

```json
{
  "cloud": "openstack",
  "vms": [
    {"name": "my-vm", "status": "ACTIVE", "ip": "203.0.113.5", "image": "ubuntu-20.04", "flavor": "m1.small"}
  ],
  "floating_ips": [
    {"address": "203.0.113.5", "attached": "my-vm", "status": "ACTIVE"}
  ],
  "reservations": [
    {"id": "lease-123", "type": "node_reservations", "status": "ACTIVE", "start": "2026-10-01T12:00:00", "end": "2026-10-08T12:00:00"}
  ]
}
```

## Behaviour notes

* Providers that do not support floating IPs or reservations will show empty lists for those sections.
* Errors retrieving data for a particular cloud are reported, but the command continues processing other clouds.
