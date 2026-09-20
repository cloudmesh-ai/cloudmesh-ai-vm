# cloudmesh-ai-vm

`cloudmesh-ai-vm` is a unified Python CLI tool (`cmc`) designed to simplify the management of Virtual Machines (VMs) across a diverse set of providers including local virtualization (Multipass, WSL2, VirtualBox) and cloud providers (OpenStack, AWS, Azure, GCP).

## 🚀 Key Features

- **Unified Interface**: Manage different cloud providers using a single consistent CLI.
- **Smart VM Lifecycle**:
    - **Automatic Naming**: VMs are named automatically using a `<username><counter>` pattern.
    - **Contextual Memory**: The tool remembers the last used VM, allowing you to run commands like `cmc vm stop` without specifying a name.
- **Provider Flexibility**:
    - **Default Cloud**: Manage your active provider via `cmc vm cloud set <cloud>` (shorthand `cmc vm set <cloud>`).
    - **Cloud Override**: Use the `--cloud` flag to temporarily use a different provider (e.g., `cmc vm start --cloud aws`).
- **Remote Execution**: Execute commands directly on your VMs using `cmc vm run <command>`.
- **Resource Discovery**: Easily list available flavors, SSH keys, and security groups directly from the CLI.
- **SSH Integration**: Generate suggested SSH configuration entries for existing VMs to enable seamless access via `ssh <hostname>`.

## 🛠️ Quick Start

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
cmc vm cloud get

# Set your default cloud
cmc vm cloud set multipass

# Start a VM (will be named user0, user1, etc.)
cmc vm start

# Run a command on the VM
cmc vm run "hostname"

# Stop the last started VM
cmc vm stop

# Start a VM on a specific cloud (override default)
cmc vm start --cloud aws

# List all VMs for current cloud
cmc vm list
```

## 📊 Provider Support Matrix

| Provider | Lifecycle (S/S/D) | Remote Exec (`run`) | Implementation Status |
| :--- | :---: | :---: | :--- |
| **Multipass** | ✅ | ✅ (Agent) | Fully Functional |
| **Lima** | ✅ | ✅ (Agent) | Fully Functional |
| **OpenStack** | ✅ | ✅ (SSH) | Fully Functional |
| **WSL2** | ✅ | ✅ (Direct) | Fully Functional |
| **VirtualBox** | ✅ | ✅ (GuestCtrl) | Fully Functional |
| **AWS** | ✅ | ✅ (SSH) | Fully Functional (via Libcloud) |
| **Azure** | ✅ | ✅ (SSH) | Fully Functional (via Libcloud) |
| **Google** | ✅ | ✅ (SSH) | Fully Functional (via Libcloud) |


## 📖 Documentation

Full documentation is available in the `/docs` folder or hosted via GitHub Pages.

- [Installation Guide](docs/installation.md)
- [Configuration Guide](docs/configuration.md)
- [CLI Reference](docs/cli.md)
- [Architecture Overview](docs/architecture.md)

## 🤝 Contributing

See [Contributing](docs/contributing.md) for guidelines on adding new providers.
