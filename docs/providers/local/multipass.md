# Multipass Provider

Multipass is a lightweight VM manager for Ubuntu, developed by Canonical. It is the default provider for `cloudmesh-ai-vm` due to its speed and simplicity.

## Configuration

In your `clouds.yaml`, you can specify the resources for Multipass VMs:

```yaml
multipass:
  image: 22.04
  cpus: 2
  memory: 4GiB
  disk: 20GiB
```

## Key Features

- **Rapid Deployment**: Start an Ubuntu VM in seconds.
- **Resource Control**: Fine-grained control over CPU, RAM, and Disk.
- **Local Networking**: VMs are accessible via local IP addresses.

## Examples

```bash
# Set Multipass as default
cmx vm set multipass

# Start a VM with default config (named <username>-<counter>)
cmx vm start

# List local Multipass VMs (header will show "VMs on multipass")
cmx vm list
```
