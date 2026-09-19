# CLI Reference

The \`cmc\` tool provides a consistent interface for managing VMs across all supported providers.

## Global Command Structure

\`\`\`bash
cmc vm <command> [options]
\`\`\`

## Global Options

The \`vm\` group supports the following global option:

- \`--cloud <cloud_name>\`: Overrides the default cloud provider for the duration of the command. For example, \`cmc vm start --cloud aws\` will start a VM on AWS even if Multipass is your default.

## Commands

### 1. Cloud Management

The `cloud` group provides commands to manage the active cloud provider.

#### `get`

Displays the current default cloud provider.

- **Usage**: `cmc vm cloud get`
- **Example**: `cmc vm cloud get`

#### `set`

Sets the default cloud provider used for all subsequent commands.

- **Usage**: `cmc vm cloud set <cloud_name>`
- **Example**: `cmc vm cloud set aws`
- **Shorthand**: `cmc vm set <cloud_name>`

### 2. VM Lifecycle

Many lifecycle commands now support **Contextual Memory**. If the \`--name\` option is omitted, the tool will target the last VM that was successfully started.

#### \`start\`

Launches a new VM.

- **Options**:
  - \`--name <name>\`: Specify a custom name. If omitted, the tool uses \`<username><counter+1>\`.
- **Examples**:
  - Default: \`cmc vm start\`
  - Custom Name: \`cmc vm start --name my-web-server\`
  - Cloud Override: \`cmc vm start --cloud aws\`

#### \`stop\`

Stops a running VM.

- **Options**:
  - \`--name <name>\`: Name of the VM to stop. If omitted, the last started VM is used.
- **Example**: \`cmc vm stop\` (Stops last VM)

#### \`delete\`

Permanently removes a VM.

- **Options**:
  - \`--name <name>\`: Name of the VM to delete. If omitted, the last started VM is used.
- **Example**: \`cmc vm delete --name my-web-server\`

#### \`suspend\`

Suspends a VM to disk (if supported by the provider).

- **Options**:
  - \`--name <name>\`: Name of the VM to suspend. If omitted, the last started VM is used.
- **Example**: \`cmc vm suspend\`

#### \`restart\`

Reboots a VM.

- **Options**:
  - \`--name <name>\`: Name of the VM to restart. If omitted, the last started VM is used.
- **Example**: \`cmc vm restart\`

#### \`login\`

Provides connection details or logs into the VM.

- **Options**:
  - \`--name <name>\`: Name of the VM. If omitted, the last started VM is used.
- **Example**: \`cmc vm login\`

### 3. Inspection & Discovery

#### \`list\`

Lists all VMs managed by the current provider.

- **Options**:
  - \`--table\`: (Default) Prints a formatted table.
  - \`--json\`: Prints output in JSON format.
  - \`--yaml\`: Prints output in YAML format.
  - \`--csv\`: Prints output in CSV format.
- **Example**: \`cmc vm list --json\`

#### \`flavors\`

Lists available hardware profiles for the current cloud.

- **Example**: \`cmc vm flavors\`

#### \`keys\`

Lists available SSH keys in the current cloud.

- **Example**: \`cmc vm keys\`

#### \`security-groups\`

Lists available security groups for the current cloud.

- **Example**: \`cmc vm security-groups\`

### 4. Networking & SSH

#### \`ssh-config\`

Generates suggested SSH configuration entries for all existing VMs in the current cloud. This allows you to connect using \`ssh <vm-name>\` without modifying your config file automatically.

- **Example**: \`cmc vm ssh-config\`

### 5. Specialized Commands

#### \`reservation\` (Chameleon Only)

Creates a hardware reservation (lease) in Chameleon Cloud.

- **Options**:
  - \`--name <name>\`: (Required) Name of the reservation.
  - \`--node-type <type>\`: (Required) e.g., \`compute_skylake\`.
  - \`--count <int>\`: (Required) Number of nodes.
  - \`--start <datetime>\`: Start date (YYYY-MM-DD HH:MM).
  - \`--end <datetime>\`: End date (YYYY-MM-DD HH:MM).
  - \`--duration <int>\`: Duration of the lease in days.
- **Examples**:
  - Duration based: \`cmc vm reservation --name my-lease --node-type compute_skylake --count 1 --duration 2\`
  - Date based: \`cmc vm reservation --name my-lease --node-type compute_skylake --count 1 --start "2026-10-01 08:00" --end "2026-10-02 08:00"\`
