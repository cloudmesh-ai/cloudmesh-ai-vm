# CLI Reference

The `cmx` tool provides a consistent interface for managing VMs across all supported providers.

## Global Command Structure

```bash
cmx vm <command> [options]
cmx key <command> [options]
```
cmx container <command> [options]


## Global Options

The `vm` group supports the following global options:

- `--cloud <cloud_name>`: Overrides the default cloud provider for the duration of the command. For example, `cmx vm start --cloud aws` will start a VM on AWS even if Multipass is your default.
- `-i, --interactive`: Enters a dedicated interactive shell for VM management, showing the active provider in the prompt.

## Commands

### 1. Provider Management

The `provider` group provides commands to manage the active cloud provider.

#### `get`

Displays the current default cloud provider.

- **Usage**: `cmx vm provider get`
- **Example**: `cmx vm provider get`

#### `set`

Sets the default cloud provider used for all subsequent commands.

- **Usage**: `cmx vm provider set <cloud_name>`
- **Example**: `cmx vm provider set aws`
- **Shorthand**: `cmx vm provider set <cloud_name>`

### 2. VM Lifecycle

Many lifecycle commands now support **Contextual Memory**. If the name is omitted, the tool will target the last VM that was successfully started.

#### `start`

Launches a new VM.

- **Options**:
  - `<name>`: (Optional) Specify a custom name. If omitted, the tool generates a name based on `<username>-<counter>` (e.g., `gregor-1`). Underscores in usernames are automatically replaced with hyphens to ensure provider compatibility.
  - `--count <int>`: Start a specified number of VMs with automatic naming.
  - `--range <range>`: Start VMs in the specified index range (e.g., `1-5`).
- **Examples**:
  - Default: `cmx vm start`
  - Custom Name: `cmx vm start my-web-server`
  - Cloud Override: `cmx vm start --cloud aws`
  - Multiple VMs: `cmx vm start --count 3`

#### `stop`

Stops a running VM.

- **Options**:
  - `<name>`: (Optional) Name of the VM to stop. If omitted, the last started VM is used.
- **Example**: `cmx vm stop` (Stops last VM)

#### `restart`

Reboots a VM.

- **Options**:
  - `<name>`: (Optional) Name of the VM to restart. If omitted, the last started VM is used.
- **Example**: `cmx vm restart`

#### `suspend`

Suspends a VM to disk (if supported by the provider).

- **Options**:
  - `<name>`: (Optional) Name of the VM to suspend. If omitted, the last started VM is used.
- **Example**: `cmx vm suspend`

#### `shelve`

Shelves a VM (OpenStack only), saving its state and freeing up resources.

- **Options**:
  - `<name>`: (Optional) Name of the VM to shelve.
- **Example**: `cmx vm shelve my-vm`

#### `unshelve`

Unshelves a previously shelved VM.

- **Options**:
  - `<name>`: (Optional) Name of the VM to unshelve.
- **Example**: `cmx vm unshelve my-vm`

#### `delete`

Permanently removes a VM.

- **Options**:
  - `<name>`: (Optional) Name of the VM to delete. If omitted, the last started VM is used.
- **Example**: `cmx vm delete --name my-web-server`

#### `login`

Provides connection details or logs into the VM.

- **Options**:
  - `<name>`: (Optional) Name of the VM. If omitted, the last started VM is used.
- **Example**: `cmx vm login`

### 3. Inspection & Discovery

#### `list`

Lists all VMs managed by the current provider. The output table includes the provider name in the header (e.g., "VMs on multipass").

- **Options**:
  - `--all`: List VMs from all enabled providers.
  - `--table`: (Default) Prints a formatted table.
  - `--json`: Prints output in JSON format.
  - `--yaml`: Prints output in YAML format.
  - `--csv`: Prints output in CSV format.
- **Example**: `cmx vm list --json`

#### `info`

Displays detailed information about a specific VM, including its current state, IP addresses, and provider-specific metadata.

- **Usage**: `cmx vm info <name>`
- **Example**: `cmx vm info my-vm`

#### `image`

Lists available VM images for the current cloud.

- **Example**: `cmx vm image`

#### `flavor`

Lists available hardware profiles for the current cloud.

- **Example**: `cmx vm flavor`

#### `key`

Manage SSH keys for the current cloud and GitHub.

- **Subcommands**:
  - `list`: List all SSH keys for the current provider.
    - `--all`: List keys from all enabled providers.
    - **Example**: `cmx key list --all`
  - `scan`: Scan for local SSH keys on the host machine.
    - `--json`: Output in JSON format.
    - **Example**: `cmx key scan`
  - `verify`: Check which local keys authenticate with GitHub.
    - **Example**: `cmx key verify`
  - `github`: Manage keys specifically on GitHub.
    - `list`: List keys currently configured in GitHub.
    - `upload <path_to_key>`: Upload a local key to GitHub.
    - **Example**: `cmx key github upload ~/.ssh/id_rsa.pub`


#### `security-group`

Manage firewall security groups for the current cloud.

- **Subcommands**:
  - `list`: List all available security groups.
  - `info <name>`: Show detailed info and rules for a specific group.
  - `create <name> [--description TEXT] [--preset PRESET]`: Create a new security group.
    - `--preset`: Apply a pre-defined rule set (`web-server`, `db-server`, `internal`).
  - `delete <name>`: Permanently remove a security group.
  - `add <vm-name> <sg-name>`: Assign a security group to a VM.
  - `remove <vm-name> <sg-name>`: Remove a security group from a VM.
  - `rule [COMMAND]`: Manage rules within a security group.
    - `rule list <sg-name>`: List all rules in the group.
    - `rule add <sg-name> --port <port> [--protocol PROTO] [--cidr CIDR]`: Add a new rule.
    - `rule remove <sg-name> <rule-id>`: Delete a rule by its ID.

- **Examples**:
  - List groups: `cmx vm security-group list`
  - Create web-ready group: `cmx vm security-group create web-sg --preset web-server`
  - Assign to VM: `cmx vm security-group add my-vm web-sg`
  - Add custom rule: `cmx vm security-group rule add web-sg --port 8080`


### 4. Networking & SSH

#### `ssh`

Starts an interactive SSH session with the VM.

- **Options**:
  - `<name>`: (Optional) Name of the VM. If omitted, the last started VM is used.
- **Example**: `cmx vm ssh` (Connects to last VM)
- **Example**: `cmx vm ssh my-web-server`

#### `run`

Executes a command on a VM via SSH without entering an interactive shell.

- **Usage**: `cmx vm run [name] "command"`
- **Example**: `cmx vm run my-vm "uptime"`
- **Example**: `cmx vm run "hostname"` (Runs on last VM)

#### `ssh-config`

Generates suggested SSH configuration entries for all existing VMs in the current cloud. This allows you to connect using `ssh <vm-name>` without modifying your config file automatically.

- **Example**: `cmx vm ssh-config`

### 5. System & Account

#### `account`

Displays account information, including usage quotas and limits for the current cloud.

- **Usage**: `cmx vm account`
- **Example**: `cmx vm account`

#### `horizon`

Opens the OpenStack Horizon dashboard in your default web browser for the active cloud provider.

- **Usage**: `cmx vm horizon [--site SITE]`
- **Example**: `cmx vm horizon`

#### `reset`

Restarts the cloud provider service or resets the local environment. For Multipass on macOS, this restarts the `multipassd` daemon.

-- **Usage**: `cmx vm reset`
-- **Example**: `cmx vm reset`

#### `doctor`

Diagnoses the active VM provider without modifying any VM resources. It performs checks for:

* Provider resolution
* Local tool requirements
* Provider configuration validation
* Provider information retrieval

**Options**

* `--strict` – Exit with a non‑zero status when any check fails.
 * `--config` – Run exhaustive configuration validation (replicates the smoke test checks for both Cloudmesh and OpenStack configuration files).

**Examples**

```bash
cmx vm doctor               # Basic health‑check
 cmx vm doctor --config # Full configuration validation
cmx vm doctor --strict      # Fail with non‑zero exit code on any error
```

### 6. Configuration

#### `config`

Manage the VM CLI configuration stored in `~/.config/cloudmesh/clouds.yaml`.

- **Subcommands**:
  - `get KEY`: Get a specific configuration value.
  - `init`: Initialize the VM CLI configuration.
  - `list`: List all current VM configuration settings.
  - `set KEY VALUE`: Set a configuration value.
- **Examples**:
  - `cmx vm config list`
  - `cmx vm config set default_cloud multipass`
\n## Container Management\n\nThe `container` group provides architectural symmetry with the `vm` group, allowing for the management of Docker containers using a consistent interface.\n\n### 1. Lifecycle\n\n#### `run`\n\nCreates and starts a new Docker container.\n\n- **Options**:\n  - `--name <name>`: (Optional) Custom name for the container.\n  - `--image <image>`: (Optional) Docker image to use. Defaults to `ubuntu:latest` or the value in `clouds.yaml`.\n  - `--dockerfile <path>`: (Optional) Path to a Dockerfile to build the image from.\n  - `--network <network>`: (Optional) Docker network to attach the container to.\n  - `[CMD]`: (Optional) Command to run inside the container.\n- **Examples**:\n  - Default: `cmx container run`\n  - Custom Image & Command: `cmx container run --name my-app --image alpine sleep 3600`\n\n#### `stop`\n\nStops a running container.\n\n- **Usage**: `cmx container stop <name>`\n- **Example**: `cmx container stop my-app`\n\n#### `restart`\n\nRestarts a container.\n\n- **Usage**: `cmx container restart <name>`\n- **Example**: `cmx container restart my-app`\n\n#### `suspend`\n\nManages the pause/resume state of a container.\n\n- **Subcommands**:\n  - `pause <name>`: Pauses the container.\n  - `resume <name>`: Resumes a paused container.\n- **Examples**:\n  - `cmx container suspend pause my-app`\n  - `cmx container suspend resume my-app`\n\n#### `delete`\n\nPermanently removes a container.\n\n- **Usage**: `cmx container delete <name>`\n- **Example**: `cmx container delete my-app`\n\n### 2. Inspection & Image Management\n\n#### `list`\n\nLists all Docker containers (running and stopped).\n\n- **Usage**: `cmx container list`\n\n#### `info`\n\nDisplays detailed information about a specific container.\n\n- **Usage**: `cmx container info <name>`\n\n#### `ip`\n\nManages and retrieves IP addresses for containers.\n\n- **Subcommands**:\n  - `list`: Lists IP addresses for all running containers.\n- **Example**: `cmx container ip list`\n\n#### `image`\n\nManage Docker images.\n\n- **Subcommands**:\n  - `pull <image>`: Pulls an image from a registry.\n  - `list`: Lists all local Docker images.\n- **Examples**:\n  - `cmx container image pull alpine:latest`\n  - `cmx container image list`\n\n### 3. Access\n\n#### `login`\n\nProvides access to the container (implementation varies by manager).\n\n- **Usage**: `cmx container login <name>`\n
