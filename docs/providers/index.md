# Providers Overview

`cloudmesh-ai-vm` supports a wide array of providers, categorized by their hosting model.

## Local Providers

Ideal for rapid development, testing, and offline work.

- **Multipass**: Canonical's lightweight Ubuntu VM manager.
- **WSL2**: Windows Subsystem for Linux.
- **VirtualBox**: Full-featured headless VM management.

## OpenStack Providers

Enterprise-grade cloud infrastructure often used in research and academic environments.

- **Jetstream**: High-performance computing (HPC) and cloud environments.
- **Chameleon Cloud**: Specialized in bare-metal and VM research with advanced reservation capabilities.

## Hyperscaler Providers

Global scale cloud services provided via the `libcloud` abstraction layer.

- **AWS EC2**: Amazon's Elastic Compute Cloud.
- **Azure VMs**: Microsoft Azure Virtual Machines.
- **Google GCE**: Google Compute Engine.
