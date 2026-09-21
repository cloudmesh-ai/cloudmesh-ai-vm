# CLI Reference

The `cmx` tool provides a consistent interface for managing VMs across all supported providers.

## Global Command Structure

```bash
cmx vm <command> [options]
```

## Global Options

The `vm` group supports the following global options:

- `--cloud <cloud_name>`: Overrides the default cloud provider for the duration of the command. For example, `cmx vm start --cloud aws` will start a VM on AWS even if Multipass is your default.
- `-i, --interactive`: Enters a dedicated interactive shell for VM management, showing the active provider in the prompt.

## Commands

### 1. Cloud Management

The `cloud` group provides commands to manage the active cloud provider.

#### `get`

Displays the current default cloud provider.

- **Usage**: `cmx vm cloud get`
- **Example**: `cmx vm cloud get`

#### `set`

Sets the default cloud provider used for all subsequent commands.

- **Usage**: `cmx vm cloud set <cloud_name>`
- **Example**: `cmx vm cloud set aws`
- **Shorthand**: `cmx vm set <cloud_name>`

### 2. VM Lifecycle

Many lifecycle commands now support **Contextual Memory**. If the name is omitted, the tool will target the last VM that was successfully started.

#### `start`

Launches a new VM.

- **Options**:
  - `<name>`: (Optional) Specify a custom name. If omitted, the tool generates a name based on `<username>-<counter>` (e.g., `gregor-1`). Underscores in usernames are automatically replaced with hyphens to ensure provider compatibility.
- **Examples**:
  - Default: `cmx vm start`
  - Custom Name: `cmx vm start my-web-server`
  - Cloud Override: `cmx vm start --cloud aws`

#### `stop`

Stops a running VM.

- **Options**:
  - `<name>`: (Optional) Name of the VM to stop. If omitted, the last started VM is used.
- **Example**: `cmx vm stop` (Stops last VM)

#### `delete`

Permanently removes a VM.

- **Options**:
  - `<name>`: (Optional) Name of the VM to delete. If omitted, the last started VM is used.
- **Example**: `cmx vm delete --name my-web-server`

#### `suspend`

Suspends a VM to disk (if supported by the provider).

- **Options**:
  - `<name>`: (Optional) Name of the VM to suspend. If omitted, the last started VM is used.
- **Example**: `cmx vm suspend`

#### `restart`

Reboots a VM.

- **Options**:
  - `<name>`: (Optional) Name of the VM to restart. If omitted, the last started VM is used.
- **Example**: `cmx vm restart`

#### `login`

Provides connection details or logs into the VM.

- **Options**:
  - `<name>`: (Optional) Name of the VM. If omitted, the last started VM is used.
- **Example**: `cmx vm login`

### 3. Inspection & Discovery

#### `list`

Lists all VMs managed by the current provider. The output table includes the provider name in the header (e.g., "VMs on multipass").

- **Options**:
  - `--table`: (Default) Prints a formatted table.
  - `--json`: Prints output in JSON format.
  - `--yaml`: Prints output in YAML format.
  - `--csv`: Prints output in CSV format.
- **Example**: `cmx vm list --json`

#### `flavors`

Lists available hardware profiles for the current cloud.

- **Example**: `cmx vm flavors`

#### `keys`

Lists available SSH keys in the current cloud.

- **Example**: `cmx vm keys`

#### `security-groups`

Lists available security groups for the current cloud.

- **Example**: `cmx vm security-groups`

### 4. Networking & SSH

#### `ssh-config`

Generates suggested SSH configuration entries for all existing VMs in the current cloud. This allows you to connect using `ssh <vm-name>` without modifying your config file automatically.

- **Example**: `cmx vm ssh-config`

### 5. Specialized Commands

#### `reservation` (Chameleon Only)

Creates a hardware reservation (lease) in Chameleon Cloud.

- **Options**:
  - `--name <name>`: (Required) Name of the reservation.
  - `--node-type <type>`: (Required) e.g., `compute_skylake`.
  - `--count <int>`: (Required) Number of nodes.
  - `--start <datetime>`: Start date (YYYY-MM-DD HH:MM).
  - `--end <datetime>`: End date (YYYY-MM-DD HH:MM).
  - `--duration <int>`: Duration of the lease in days.
- **Examples**:
  - Duration based: `cmx vm reservation --name my-lease --node-type compute_skylake --count 1 --duration 2`
  - Date based: `cmx vm reservation --name my-lease --node-type compute_skylake --count 1 --start "2026-10-01 08:00" --end "2026-10-02 08:00"`
