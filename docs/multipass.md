# Multipass Provider

The Multipass provider allows Cloudmesh to manage local virtual machines using the [Multipass](https://multipass.run/) CLI tool.

## Feature Comparison

The following table compares the native Multipass CLI functionality with the capabilities provided by the Cloudmesh AI VM Multipass provider.

| Feature | Native Multipass CLI | Cloudmesh Provider | Notes |
| :--- | :---: | :---: | :--- |
| **VM Creation** | `multipass launch` | `start()` | Supports custom CPU, Memory, and Disk configurations. |
| **VM Starting** | `multipass start` | `start()` | Automatically detects if VM exists and uses `start` vs `launch`. |
| **VM Stopping** | `multipass stop` | `stop()` | Standard stop operation. |
| **VM Deletion** | `multipass delete` | `delete()` | Performs `delete` followed by `purge` for clean removal. |
| **VM Restart** | `multipass stop` $\rightarrow$ `start` | `restart()` | Orchestrates stop and start in one call. |
| **List VMs** | `multipass list` | `list()` | Parses output into a structured list of dictionaries. |
| **VM Information**| `multipass info` | `info()` | Retrieves detailed metadata about a specific VM. |
| **Image Discovery**| `multipass find` | `get_images()` | Uses JSON output for robust image and alias discovery. |
| **Hardware Profiles**| N/A | `get_flavors()` | Provides predefined size profiles (default, medium, large). |
| **SSH Key Mgmt** | Manual / Internal | `upload_key()` / `delete_key()` | Manages `authorized_keys` with named labels for easy removal. |
| **Remote Execution**| `multipass exec` | `run_command()` | Simplified interface for executing shell commands in the VM. |
| **Resource Mgmt** | Manual | `shelve()` / `unshelve()` | Implements shelving by stopping VMs to release compute resources. |
 | **Daemon Reset** | `launchctl` (macOS) | `reset()` | Integrated reset for the Multipass background service on macOS. |

**Implementation Note:** The Multipass provider now uses the unified project logger (`cloudmesh.ai.vm.logger`) for all informational and error messages, replacing previous `self.print` calls.

## Configuration

The provider is configured via the `clouds.yaml` file:

```yaml
clouds:
  multipass:
    image: "22.04" # Default image to use for launches
    cpus: 2
    memory: "4GiB"
    disk: "20GiB"
```
