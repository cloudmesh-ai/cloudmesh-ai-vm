# Multipass Provider

The Multipass provider allows you to manage lightweight Ubuntu virtual machines on your local machine. It leverages the Canonical Multipass daemon to handle VM orchestration, providing a fast and consistent development environment.

## Overview

Multipass is used to create and manage local VMs. Unlike traditional virtualization, Multipass is designed for rapid deployment of Ubuntu instances, making it ideal for testing cloud-like environments locally.

## Configuration

The Multipass provider uses the following configuration settings in `clouds.yaml`:

| Setting | Description | Default |
| :--- | :--- | :--- |
| `image` | The Ubuntu image version to use for launches. | `22.04` |
| `cpus` | Number of CPU cores assigned to each VM. | Host default |
| `memory` | Amount of RAM assigned to each VM (e.g., `2GiB`). | Host default |
| `disk` | Disk size assigned to each VM (e.g., `10GiB`). | Host default |

### Example Configuration
```yaml
clouds:
  multipass:
    image: "24.04"
    cpus: 2
    memory: "4GiB"
    disk: "20GiB"
```

## Command Reference

### VM Lifecycle
- **`cmx vm start [NAME]`**: Launches a new VM. If no name is provided, one is automatically generated using the `{username}-{counter}` pattern.
- **`cmx vm stop [NAME]`**: Stops a running VM.
- **`cmx vm restart [NAME]`**: Stops and then starts a VM.
- **`cmx vm delete [NAME]`**: Deletes a VM and purges its data from the system.

### Resource Discovery
- **`cmx vm list`**: Displays all local Multipass VMs, including their status and IP addresses.
- **`cmx vm info [NAME]`**: Shows detailed internal metadata for a specific VM.
- **`cmx vm image`**: Lists available Ubuntu images that can be used for launches.

### VM Interaction
- **`cmx vm run [NAME] [COMMAND]`**: Executes a command inside the VM via the Multipass agent.
- **`cmx vm login [NAME]`**: Provides the SSH connection string to access the VM.
- **`cmx vm upload-key [PATH] --name [NAME]`**: Uploads a public SSH key to the VM for passwordless access.

## Advanced Features

### Local Environment Portability
The Multipass provider is designed to be portable across different Windows shells. It automatically detects whether it should use `multipass.exe` or `multipass` based on the environment (CMD, PowerShell, or Git Bash), ensuring consistent behavior regardless of how the CLI is invoked.

### Daemon Management
On macOS, you can reset the Multipass daemon if it becomes unresponsive using:
`cmx vm reset`
This performs a `kickstart` of the `com.canonical.multipassd` system service.
`