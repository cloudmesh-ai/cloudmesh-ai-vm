# CLI Reference

The \`cmc\` tool provides a consistent interface for managing VMs across all supported providers.

## Global Command Structure

\`\`\`bash
cmc vm <command> [options]
\`\`\`

## Commands

### 1. Cloud Management

#### \`set\`

Sets the default cloud provider used for all subsequent commands.

- **Usage**: \`cmc vm set <cloud_name>\`
- **Example**: \`cmc vm set aws\`

### 2. VM Lifecycle

#### \`start\`

Launches a new VM.

- **Options**:
  - \`--name <name>\`: Specify a custom name. If omitted, the tool uses \`<username><counter+1>\`.
- **Examples**:
  - Default: \`cmc vm start\`
  - Custom Name: \`cmc vm start --name my-web-server\`

#### \`stop\`

Stops a running VM.

- **Options**:
  - \`--name <name>\`: Name of the VM to stop.
- **Example**: \`cmc vm stop --name my-web-server\`

#### \`delete\`

Permanently removes a VM.

- **Options**:
  - \`--name <name>\`: Name of the VM to delete.
- **Example**: \`cmc vm delete --name my-web-server\`

#### \`suspend\`

Suspends a VM to disk (if supported by the provider).

- **Options**:
  - \`--name <name>\`: Name of the VM to suspend.
- **Example**: \`cmc vm suspend --name my-web-server\`

#### \`restart\`

Reboots a VM.

- **Options**:
  - \`--name <name>\`: Name of the VM to restart.
- **Example**: \`cmc vm restart --name my-web-server\`

#### \`login\`

Provides connection details or logs into the VM.

- **Options**:
  - \`--name <name>\`: Name of the VM.
- **Example**: \`cmc vm login --name my-web-server\`

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

### 4. Specialized Commands

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
