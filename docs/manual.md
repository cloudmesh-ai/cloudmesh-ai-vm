# VM Management Manual

The `cmx vm` command set provides a unified interface for managing Virtual Machines across multiple local and cloud providers.

## Global Options

These options can be used with any `cmx vm` command:

| Option | Description |
| :--- | :--- |
| `--cloud TEXT` | Override the default cloud provider. |
| `--debug` | Enable debug logging for troubleshooting. |
| `--verbose` | Print raw subprocess/SSH commands. |
| `-i, --interactive` | Enter interactive mode. |

---

## Subcommands

### Configuration (`cmx vm config`)
Manage the CLI configuration stored in `~/.config/cloudmesh/clouds.yaml`.

- **`get KEY`**: Get a specific configuration value.
- **`init`**: Initialize the VM CLI configuration.
- **`list`**: List all current VM configuration settings.
- **`set KEY VALUE`**: Set a configuration value.

### Lifecycle Management

- **`start [NAME]`**: Starts or launches a VM. If no name is provided, a name is generated based on `{username}-{counter}`.
  - *Example*: `cmx vm start my-vm`
- **`stop [NAME]`**: Stops a running VM.
  - *Example*: `cmx vm stop my-vm`
- **`restart [NAME]`**: Restarts a VM.
  - *Example*: `cmx vm restart my-vm`
- **`suspend [NAME]`**: Suspends a VM to disk.
- **`shelve [NAME]`**: Shelve the VM (OpenStack only).
- **`unshelve [NAME]`**: Unshelve the VM (OpenStack only).
- **`delete [NAME]`**: Deletes a VM from the provider.
  - *Example*: `cmx vm delete my-vm`

### Resource Discovery

- **`list`**: List VM resources.
  - `cmx vm list vms`: List all VMs in the active cloud.
  - `cmx vm list regions`: List available regions for the current provider.
- **`info NAME`**: Get detailed information (IPs, State, etc.) about a specific VM.
- **`images`**: List available VM images for the active provider.
- **`flavors`**: List available VM flavors/sizes.
- **`security_groups`**: List available security groups.

### Provider Management (`cmx vm providers`)
Manage the cloud providers available to the tool.

- **`get`**: Get the current default cloud provider.
- **`set PROVIDER`**: Set the default cloud provider.
- **`list`**: List all supported providers and their configuration status.
- **`info`**: Display detailed information about the active provider.

### Key Management (`cmx vm key`)
Manage SSH keys for VM access.

- **`upload KEY_PATH`**: Upload a public SSH key to the cloud provider.
  - Use `--name TEXT` to provide a custom name.
- **`list`**: List all SSH keys for the current provider.
- **`delete KEY_NAME`**: Delete an SSH key from the provider.

### VM Interaction & Utilities

- **`run [NAME] [COMMAND]`**: Executes a command on a VM via SSH.
  - *Example*: `cmx vm run my-vm "ls -la /home"`
- **`ssh_config [NAME]`**: Generate a local SSH configuration snippet for easy access.
