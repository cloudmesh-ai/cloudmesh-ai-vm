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

- **`start [NAME]`**: Starts or launches a VM.
  - **Options**:
    - `--count <int>`: Launch a specific number of VMs with automatic naming.
    - `--range <range>`: Launch VMs in the specified index range (e.g., `1-5`).
  - If no name is provided, a name is generated based on `{username}-{counter}`.
  - *Example*: `cmx vm start my-vm`
  - *Example*: `cmx vm start --count 3`
- **`stop [NAME]`**: Stops a running VM.
  - *Example*: `cmx vm stop my-vm`
- **`restart [NAME]`**: Restarts a VM.
  - *Example*: `cmx vm restart my-vm`
- **`suspend [NAME]`**: Suspends a VM to disk.
- **`shelve [NAME]`**: Shelve the VM (OpenStack only).
- **`unshelve [NAME]`**: Unshelve the VM (OpenStack only).
- **`delete [NAME]`**: Deletes a VM from the provider.
  - *Example*: `cmx vm delete my-vm`
- **`reset [NAME]`**: Reset a VM or restart the provider service (e.g., Multipass daemon).
  - *Example*: `cmx vm reset`

### Resource Discovery

- **`list`**: List VM resources.
  - **Options**:
    - `--all`: List resources from all enabled providers.
  - `cmx vm list vms`: List all VMs in the active cloud.
  - `cmx vm list regions`: List available regions for the current provider.
- **`info NAME`**: Get detailed information (IPs, State, etc.) about a specific VM.
- **`image`**: List available VM image for the active provider.
- **`flavor`**: List available VM flavor/sizes.
- **`security-group`**: Manage firewall security groups.
  - `list`: List all available security groups.
  - `info <name>`: Get detailed information and rules.
  - `create <name> [--preset PRESET]`: Create a new group (presets: `web-server`, `db-server`, `internal`).
  - `delete <name>`: Remove a security group.
  - `add <vm> <sg>`: Assign a group to a VM.
  - `remove <vm> <sg>`: Unassign a group from a VM.
  - `rule [list|add|remove]`: Manage rules within a group.

### Provider Management (`cmx vm provider`)
Manage the cloud providers available to the tool.

- **`get`**: Get the current default cloud provider.
- **`set PROVIDER`**: Set the default cloud provider.
- **`list`**: List all supported providers and their configuration status.
- **`info`**: Display detailed information about the active provider.
  - For the **WSL2 provider**, the tool automatically detects the best available binary (`wsl.exe` or `wsl`) for compatibility across Windows CMD, PowerShell, Git Bash, and WSL-native environments.

### Key Management (`cmx key`)
Manage SSH keys for VM access.

- **`upload KEY_PATH`**: Upload a public SSH key to the cloud provider.
  - Use `--name TEXT` to provide a custom name.
- **`list`**: List all SSH keys for the current provider.
- **`delete KEY_NAME`**: Delete an SSH key from the provider.

### VM Interaction & Utilities

- **`run [NAME] [COMMAND]`**: Executes a command on a VM via SSH.
  - *Example*: `cmx vm run my-vm "ls -la /home"`
- **`ssh [NAME]`**: Starts an interactive SSH session with the VM.
  - *Example*: `cmx vm ssh my-vm`
- **`login [NAME]`**: Get connection info or log into the VM.
  - *Example*: `cmx vm login my-vm`
- **`ssh-config [NAME]`**: Generate a local SSH configuration snippet for easy access.

### Account & System

- **`account`**: View account information, including usage quotas and limits for the current cloud.
  - *Example*: `cmx vm account`
- **`horizon`**: Open the OpenStack Horizon dashboard in your default web browser for the active cloud provider.
101 | - **`reset`**: Restart the cloud provider service or reset the local environment (e.g., restart Multipass daemon on macOS).
102 |   - *Example*: `cmx vm reset`
103 |
104 | - **`status [--cloud=CLOUD] [--json]`**: Shows a summary of the current state of the selected cloud (or all enabled clouds when `--cloud` is omitted). The output contains three sections:
105 |   - **Running VMs** – name, status, IP, image, flavor, etc.
106 |   - **Floating IPs** – address, attached VM, status.
107 |   - **Reservations / Leases** – id, type, status, start, end.
108 |   Use `--json` to emit the same information as a JSON document.
109 |   **Examples**:
110 |   ```bash
111 |   cmx vm status
112 |   cmx vm status --cloud openstack
113 |   cmx vm status --json
114 |   ```
115 |
116 | - **`purge [--cloud=CLOUD] [--yes | -y]`**: Deletes all VMs, releases all floating IPs, and removes all reservations for the target cloud (or for every enabled cloud when the option is omitted). A safety confirmation prompt is required unless the user supplies `--yes` / `-y` to skip the prompt for scripted usage.
117 |   **Examples**:
118 |   ```bash
119 |   cmx vm purge                # interactive, all clouds
120 |   cmx vm purge --cloud chameleon
121 |   cmx vm purge -y             # non‑interactive, all clouds
122 |   ```

