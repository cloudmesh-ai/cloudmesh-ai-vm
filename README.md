# cloudmesh-ai-vm

## Key Features

- **Unified Interface**: Manage different cloud providers using a single consistent CLI.
- **Smart VM Lifecycle**:
    - **Automatic Naming**: VMs are named automatically using a `<username>-<counter>` pattern (e.g., `gregor-1`).
    - **Contextual Memory**: The tool remembers the last used VM (the most recently started or accessed instance), allowing you to run commands like `cmx vm stop` without specifying a name.
- **Provider Flexibility**:
    - **Default Cloud**: Manage your active provider via `cmx vm provider set <cloud>`.
    - **Cloud Override**: Use the `--cloud` flag to temporarily use a different provider (e.g., `cmx vm start --cloud aws`).
 - **Floating IP Control**: The `cmx vm start` command now supports a `--noip` flag to start a VM without allocating a public floating IP, saving scarce IP resources.
 - **Floating IP Descriptions**: When a floating IP is allocated, its ``description`` field is set to the Cloudmesh username (or a generic placeholder) to aid in resource tracking and billing.
- **Remote Execution**: Execute commands directly on your VMs using `cmx vm run <command>`.
- **SSH Key Management**: Scan for local SSH keys, verify their GitHub authentication status, and manage keys on GitHub (list and upload) directly from the CLI.
- **Security Management**: Create, assign, and manage firewall rules for your VMs directly from the CLI (with smart-presets for web and database servers).
- **SSH Integration**: Generate suggested SSH configuration entries for existing VMs to enable seamless access via `ssh <hostname>`.
- **Interactive Shell**: Enter a dedicated VM management shell using `cmx vm -i`.
- **SDK Native**: OpenStack providers (Chameleon, Jetstream) are implemented using the official OpenStack SDK for maximum stability and feature support.
- **Interactive Shell**: Enter a dedicated VM management shell using `cmx vm -i`.
- **SDK Native**: OpenStack providers (Chameleon, Jetstream) are implemented using the official OpenStack SDK for maximum stability and feature support.
 20 |  - **Environment Diagnostics**: Use `cmx vm doctor` to validate provider requirements, configuration, and diagnostic information. Add the `--config` flag to run exhaustive configuration validation (replicates the smoke test).

The full documentation is available at: <https://cloudmesh-ai.github.io/cloudmesh-ai-vm/>

## Quick Start

### 1. Installation

```bash
git clone https://github.com/cloudmesh-ai/cloudmesh-ai-vm.git
cd cloudmesh-ai-vm
pip install -e .
```

### 2. Configuration

Configure your credentials in `~/.config/cloudmesh/clouds.yaml`. See the [Configuration Guide](docs/configuration.md) for details.

- **Container Management**: Full architectural symmetry with VM management for Docker containers.
    - **Lifecycle**: Start, stop, restart, suspend (pause), resume (unpause), and delete containers.
    - **Image Management**: Pull Docker images and list available images.
    - **Networking**: Retrieve and list IP addresses for all running containers.
### 2. Basic Usage

```bash
# Check current default cloud
cmx vm provider get

# Set your default cloud
cmx vm provider set multipass

# Start a VM (will be named username-1, username-2, etc.)
cmx vm start

# Start a VM without allocating a floating IP (useful when you don't need external access)
cmx vm start --noip

# Run a command on the VM
cmx vm run "hostname"

# Log into the VM (interactive)
cmx vm login

# Start an interactive SSH session
cmx vm ssh

# Stop the last started VM
cmx vm stop

# Start a VM on a specific cloud (override default)
cmx vm start --cloud aws

# List all VMs for current cloud
cmx vm list
```

For a detailed description of the floating‑IP workflow, see the documentation page:
`docs/floating-ip-workflow.md`.
cmx vm list
\n# Docker Container Management\n\n```bash\n# Run a container with a custom command (to keep it alive)\ncmx container run --name my-cont --image alpine sleep 3600\n\n# List running containers\ncmx container list\n\n# Get container info\ncmx container info my-cont\n\n# List IPs of all running containers\ncmx container ip list\n\n# Lifecycle management\ncmx container restart my-cont\ncmx container suspend pause my-cont\ncmx container suspend resume my-cont\n\n# Image management\ncmx container image pull alpine:latest\ncmx container image list\n\n# Stop and delete\ncmx container stop my-cont\ncmx container delete my-cont\n```\n

# Manage SSH keys (Scan local, verify GitHub, or upload to GitHub)
cmx key scan
cmx key github upload ~/.ssh/id_rsa.pub

# Manage Security Groups (Example: create a web-server preset)
cmx vm security-group create --name web-sg --preset web

# Enter interactive VM shell
cmx vm -i
```

## VM Doctor & Troubleshooting

If you encounter issues with provider connectivity, missing dependencies, or configuration errors, use the `cmx vm doctor` command before performing lifecycle operations.

`cmx vm doctor` provides a non-destructive health check for the active VM provider.

The command performs the following checks:
- **Provider Resolution**: Verifies that the requested or configured provider can be loaded.
- **Requirements**: Checks whether required local tools and provider dependencies are available.
- **Configuration**: Runs provider configuration validation when supported.
- **Provider Info**: Retrieves provider diagnostic information when local requirements are available.

Run Doctor using the currently selected provider:
`cmx vm doctor`

Check a specific provider:
```bash
cmx vm doctor --cloud multipass
cmx vm doctor --cloud aws
cmx vm doctor --cloud openstack
```

For scripts, automated validation, or CI workflows, use strict mode:
`cmx vm doctor --cloud multipass --strict`

With `--strict`, Doctor returns exit code 1 when one or more required checks fail. A healthy provider returns exit code 0.

Example:

```bash
VM Doctor: multipass

Provider        PASS   Resolved provider: multipass
Requirements    FAIL   One or more required provider tools are unavailable.
Configuration   PASS   No configuration problems detected.
Provider Info   SKIP   Skipped because provider requirements are unavailable.

Doctor result: NEEDS ATTENTION
```

Doctor does not create, start, stop, restart, suspend, or delete virtual machines.

## Provider Support Matrix

| Provider | Lifecycle (S/S/D) | Remote Exec (`run`) | Implementation Status |
| :--- | :---: | :---: | :--- |
| **Multipass** | ✅ | ✅ (Agent) | 🟢 |
| **Lima** | ✅ | ✅ (Agent) | 🟢 |
| **OpenStack** | ✅ | ✅ (SSH) | 🟢 (via OpenStack SDK) |
| **WSL2** | ✅ | ✅ (Direct) | 🟢 |
| **VirtualBox** | ✅ | ✅ (GuestCtrl) | 🟢 |
| **AWS** | ✅ | ✅ (SSH) | 🟢 (via Libcloud) |
| **Azure** | ✅ | ✅ (SSH) | 🟢 (via Libcloud) |
| **Google** | ✅ | ✅ (SSH) | 🟢 (via Libcloud) |

🟡 = has been implemented but not tested. We anticipate issues

## Documentation

Full documentation is available in the `/docs` folder or hosted via GitHub Pages.

- [Installation Guide](docs/installation.md)
- [Configuration Guide](docs/configuration.md)
- [CLI Reference](docs/cli.md)
- [Architecture Overview](docs/architecture.md)

## Testing

The project uses a tiered testing strategy to ensure stability across multiple cloud and local providers:

### Testing Structure

- `tests/unit`: **Unit Tests**. High-isolation tests that use mocks to verify internal logic and CLI behavior without requiring external infrastructure.
- `tests/integration`: **Integration Tests**. End-to-end tests that perform real operations against actual cloud infrastructure.
- `tests/compliance`: **Compliance Suite**. Ensures every provider implements a consistent interface and meets the minimum functional baseline. Includes "Scenario Tests" for end-to-end user flows.
### Running Smoke Tests

Smoke tests are quick, high-level checks to verify that the CLI and providers load and execute basic commands without crashing.

```bash
# Run all smoke tests
PYTHONPATH=. pytest tests/smoke
```

#### Configuration Validation Smoke Test

The `tests/smoke/test_config.py` smoke test validates the presence and correctness of both
Cloudmesh and OpenStack configuration files (`~/.config/cloudmesh/clouds.yaml` and
`~/.config/openstack/clouds.yaml`). It checks that the YAML files are parsable and that
required provider sections contain the necessary keys.

Run this test individually with:

```bash
PYTHONPATH=. pytest tests/smoke/test_config.py
```

It is also included when running the full smoke suite (`pytest tests/smoke`).
#### Benchmark Results
Smoke tests automatically capture performance benchmarks (timers) and system information. These results are stored in a centralized repository for tracking improvements across different environments and users.

**Requirements:**
To save results, you must have the results repository cloned locally at the project root's sibling directory:
```bash
git clone git@github.com:cloudmesh/cloudmesh-ai-vm-results.git ..
```

**Storage Path:**
Results are saved as `.txt` and `.json` files in the following structure:
`../cloudmesh-ai-vm-results/<username>/smoke/`

The `username` is retrieved from your `~/.config/cloudmesh/clouds.yaml` configuration file.

Tests can be run in two modes:


- **Unit Mode (Default)**: Uses a standardized `MockDriver` to verify return types and basic logic without needing cloud credentials, ensuring a reliable functional baseline across all providers.
  ```bash
  PYTHONPATH=. pytest -s tests/compliance/test_compliance.py
  ```

- **Integration Mode**: Performs real operations against actual cloud infrastructure. Requires valid credentials in your configuration.
  ```bash
  PYTHONPATH=. COMPLIANCE_MODE=integration pytest -s tests/compliance/test_compliance.py
  ```

The compliance suite also includes **Scenario Tests** (such as the "Zero-to-Hero" flow) to validate that the end-to-end user experience—from configuration validation to VM deletion—is consistent across all supported cloud and local providers.

## Contributing

See [Contributing](docs/contributing.md) for guidelines on adding new providers.

**Note**: To be added to the `CONTRIBUTORS.md` file, please submit a separate Pull Request specifically for that purpose.

---
