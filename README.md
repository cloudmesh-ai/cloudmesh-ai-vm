# cloudmesh-ai-vm

`cloudmesh-ai-vm` is a unified Python CLI tool (`cmx`) designed to simplify the management of Virtual Machines (VMs) across a diverse set of providers including local virtualization (Multipass, WSL2, VirtualBox) and cloud providers (OpenStack, AWS, Azure, GCP).

## Key Features

- **Unified Interface**: Manage different cloud providers using a single consistent CLI.
- **Smart VM Lifecycle**:
    - **Automatic Naming**: VMs are named automatically using a `<username>-<counter>` pattern (e.g., `gregor-1`).
    - **Contextual Memory**: The tool remembers the last used VM, allowing you to run commands like `cmx vm stop` without specifying a name.
- **Provider Flexibility**:
    - **Default Cloud**: Manage your active provider via `cmx vm provider set <cloud>`.
    - **Cloud Override**: Use the `--cloud` flag to temporarily use a different provider (e.g., `cmx vm start --cloud aws`).
- **Remote Execution**: Execute commands directly on your VMs using `cmx vm run <command>`.
- **Resource Discovery**: Easily list available flavors, SSH keys, and security groups directly from the CLI.
- **SSH Integration**: Generate suggested SSH configuration entries for existing VMs to enable seamless access via `ssh <hostname>`.
- **Interactive Shell**: Enter a dedicated VM management shell using `cmx vm -i`.
- **Libcloud Native**: OpenStack providers (Chameleon, Jetstream) are implemented strictly using the Libcloud driver for improved stability and consistency.

## Quick Start

### 1. Installation

```bash
git clone https://github.com/your-repo/cloudmesh-ai-vm.git
cd cloudmesh-ai-vm
pip install -e .
```

### 2. Configuration

Configure your credentials in `~/.config/cloudmesh/clouds.yaml`. See the [Configuration Guide](docs/configuration.md) for details.

### 3. Basic Usage

```bash
# Check current default cloud
cmx vm provider get

# Set your default cloud
cmx vm provider set multipass

# Start a VM (will be named username-1, username-2, etc.)
cmx vm start

# Run a command on the VM
cmx vm run "hostname"

# Stop the last started VM
cmx vm stop

# Start a VM on a specific cloud (override default)
cmx vm start --cloud aws

# List all VMs for current cloud
cmx vm list

# Enter interactive VM shell
cmx vm -i
```

## Provider Support Matrix

| Provider | Lifecycle (S/S/D) | Remote Exec (`run`) | Implementation Status |
| :--- | :---: | :---: | :--- |
| **Multipass** | ✅ | ✅ (Agent) |  🟢 |
| **Lima** | ✅ | ✅ (Agent) | 🟢 |
| **OpenStack** | ✅ | ✅ (SSH) |  🟢 (via Libcloud) |
| **WSL2** | ✅ | ✅ (Direct) | 🟡 |
| **VirtualBox** | ✅ | ✅ (GuestCtrl) | 🟡 |
| **AWS** | ✅ | ✅ (SSH) | 🟡 (via Libcloud) |
| **Azure** | ✅ | ✅ (SSH) | 🟡 (via Libcloud) |
| **Google** | ✅ | ✅ (SSH) | 🟡 (via Libcloud) |

🟡 = has been implemented but not tested. We anticipate issues

## 📖 Documentation

Full documentation is available in the `/docs` folder or hosted via GitHub Pages.

- [Installation Guide](docs/installation.md)
- [Configuration Guide](docs/configuration.md)
- [CLI Reference](docs/cli.md)
- [Architecture Overview](docs/architecture.md)

## Contributing

See [Contributing](docs/contributing.md) for guidelines on adding new providers.
