# Welcome to cloudmesh-ai-vm

`cloudmesh-ai-vm` is a unified Python CLI tool (`cmc`) designed to simplify the management of Virtual Machines (VMs) across a diverse set of providers. Whether you are using local virtualization for development or scaling in the cloud for production, `cmc` provides a consistent interface for the entire VM lifecycle.

## Key Value Propositions

- **One Interface, Many Clouds**: Stop learning different CLI tools for AWS, Azure, Multipass, and OpenStack. Use `cmc` for all of them.
- **Automated Workflow**: Built-in automatic naming and counter management to avoid name collisions when launching multiple VMs.
- **Developer Focused**: Designed for AI researchers and developers who need to spin up and tear down environments quickly across different infrastructures.
- **Extensible**: Based on the **Provider Pattern**, making it trivial to add support for new cloud services.

## Supported Providers

| Category | Providers |
| :--- | :--- |
| **Local** | Multipass, WSL2, VirtualBox |
| **OpenStack** | Jetstream, Chameleon Cloud |
| **Hyperscalers** | AWS EC2, Azure VMs, Google Compute Engine |

## Quick Start

1. **Install** the tool and its dependencies.
2. **Configure** your credentials in `~/.config/cloudmesh/clouds.yaml`.
3. **Set** your default provider:
   ```bash
   cmx vm set multipass
   ```
4. **Launch** your first VM:
   ```bash
   cmx vm start
   ```

See the [Installation Guide](installation.md) to get started.
