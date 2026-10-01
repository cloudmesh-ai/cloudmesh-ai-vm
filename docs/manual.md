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

Set `CLOUDMESH_VM_CONFIG` to select a separate configuration file for tests.
`init` preserves existing values. `set` parses YAML values, including integers
and booleans. `get` accepts zero and false values and fails for a missing key.

- **`get KEY`**: Get a specific configuration value.
- **`init`**: Initialize the VM CLI configuration.
- **`list`**: List all current VM configuration settings.
- **`set KEY VALUE`**: Set a configuration value.

### Lifecycle Management

- **`start [NAME]`**: Starts or launches a VM. If no name is provided, a name is generated based on `{username}-{counter}`.
  - *Example*: `cmx vm start my-vm`
  - `--name TEXT` supplies an exact name without incrementing the counter.
  - `--count N` reserves N automatic names; `--range A-B` supplies named indices.
  - Use one target selector. Automatic names skip existing instances. Reservations
    can consume a counter value even when a launch fails.
  - Multipass resumes stopped/suspended instances and does not relaunch a running name.
- **`stop [NAME]`**: Stops a running VM.
  - *Example*: `cmx vm stop my-vm`
- **`restart [NAME]`**: Restarts a VM.
  - *Example*: `cmx vm restart my-vm`
- **`suspend [NAME]`**: Suspends a VM to disk.
  - Multipass resumes it with `start NAME`; suspension is distinct from shelving.
- **`shelve [NAME]`**: Shelve the VM (OpenStack only).
- **`unshelve [NAME]`**: Unshelve the VM (OpenStack only).
- **`delete [NAME]`**: Deletes a VM from the provider.
  - *Example*: `cmx vm delete my-vm`
- **`reset [NAME]`**: Reset a VM or restart the provider service (e.g., Multipass daemon).
  - *Example*: `cmx vm reset multipass`
  - On macOS Multipass this operates on the daemon and may affect other VMs.

### Resource Discovery

- **`list`**: List VM resources.
  - `cmx vm list vms`: List all VMs in the active cloud.
  - `cmx vm list --json`, `--yaml`, `--csv`, or `--table`: Select an output format.
  - `cmx vm list vms --format json`: Equivalent format option on the VM subcommand.
  - `cmx vm list --all --json`: Export VM records from enabled providers.
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

### Key Management (`cmx vm key`)
Manage SSH keys for VM access.

- **`upload KEY_PATH`**: Upload a public SSH key to the cloud provider.
  - Use `--name TEXT` to provide a custom name.
- **`list`**: List all SSH keys for the current provider.
- **`delete KEY_NAME`**: Delete an SSH key from the provider.

### VM Interaction & Utilities

- **`run [NAME] [COMMAND]`**: Executes a command on a VM through its provider.
  - *Example*: `cmx vm run my-vm "ls -la /home"`
  - Multipass uses `multipass exec NAME -- sh -lc COMMAND`. Nonzero guest exits
    fail the CLI; a successful command with empty output succeeds.
- **`ssh [NAME]`**: Starts an interactive SSH session with the VM.
  - *Example*: `cmx vm ssh my-vm`
  - Multipass uses its managed shell instead of assuming a user SSH key.
- **`login [NAME]`**: Get connection info or log into the VM.
  - *Example*: `cmx vm login my-vm`
- **`ssh-config`**: Request a provider-generated SSH configuration snippet.
  - It takes no VM-name argument. Multipass configuration generation remains unsupported.

### Account & System

- **`account`**: View account information, including usage quotas and limits for the current cloud.
  - *Example*: `cmx vm account`
- **`reset`**: Restart the cloud provider service or reset the local environment (e.g., restart Multipass daemon on macOS).
  - *Example*: `cmx vm reset`
  - For Multipass use an explicit provider label, `cmx vm reset multipass`.

### Multipass validation scope

See the [Multipass guide](providers/local/multipass.md) for command coverage and
`tests/bin/verify_multipass_week5.sh` for disposable lifecycle/naming verification.
Interactive shells and daemon reset need separate manual checks. Unsupported
shelve/unshelve, cloud-specific account/network operations, and other providers
must not be counted as successfully implemented by a passing local script.
