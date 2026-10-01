# Multipass Provider

Multipass is a lightweight VM manager for Ubuntu, developed by Canonical. It is the default provider for `cloudmesh-ai-vm` due to its speed and simplicity.

## Configuration

In your `clouds.yaml`, you can specify the resources for Multipass VMs:

```yaml
default_cloud: multipass
username: user
clouds:
  multipass:
    image: "24.04"
    cpus: 2
    memory: 2G
    disk: 10G
```

## Key Features

- **Rapid Deployment**: Start an Ubuntu VM in seconds.
- **Resource Control**: Fine-grained control over CPU, RAM, and Disk.
- **Local Networking**: VMs are accessible via local IP addresses.

## Examples

```bash
# Set Multipass as default
cmx vm provider set multipass

# Start a VM with default config (named <username>-<counter>)
cmx vm start

# List local Multipass VMs (header will show "VMs on multipass")
cmx vm list vms
```

## Lifecycle and troubleshooting

Configuration is stored in `~/.config/cloudmesh/clouds.yaml`.
Provider settings belong under `clouds.multipass`.

Use a new name for a disposable test VM:

```bash
cmx vm start multipass-demo
cmx vm list vms
cmx vm restart multipass-demo
cmx vm stop multipass-demo
multipass info multipass-demo
multipass start multipass-demo

# Permanently remove only this test VM.
cmx vm delete multipass-demo
multipass list
```

Deletion uses `multipass delete --purge NAME`, without a global purge.

The local verification recorded 8 passed and 3 failed.
Two successful checks used Multipass directly.
The stopped state was confirmed, and the final inventory retained the other VMs.

| Command | Current limitation |
| --- | --- |
| `cmx vm info NAME` | Multipass provider does not implement `info`. |
| `cmx vm run NAME hostname` | Provider does not implement `run_command`. |
| `cmx vm start NAME` for an existing VM | Attempts another launch; use `multipass start NAME` to resume. |

Naming counters, shelve/unshelve, and the remaining commands were not validated.
An intermittent editable-install import failure still needs investigation.
A regular installation allowed the latest verification to proceed.
