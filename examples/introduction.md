# Introduction to Cloud VM Examples

Welcome to the Cloud VM Examples library. This directory contains a comprehensive set of guides designed to take you from your first virtual machine to a professional, hardened, and scalable cloud architecture.

Because the topics range from low-level networking to high-level orchestration, we recommend following the material in the order presented below.

## Recommended Learning Path

### Phase 1: Foundations (Provisioning & Basic Connectivity)
Start here to understand how VMs are created locally and in the cloud, and how to first establish a connection.
- **[VM Frameworks](vm-frameworks.md)**: Comparing local hypervisors for Linux, Windows, Mac, and Pi.
    - *Deep Dive*: **[VirtualBox Detailed Guide](virtualbox.md)**
    - *Deep Dive*: **[Multipass Detailed Guide](multipass.md)**
- **[OpenStack](openstack.md)**: Understanding multi-cloud VM management.
- **[Chameleon](chameleon.md)**: Bare-metal provisioning basics.
- **[Config](config.md)**: Best practices for initial cloud connectivity.
- **[Lazy-Loading](lazy-loading.md)**: Understanding plugin architectures for SDKs.

### Phase 2: Networking & Perimeter Security
Once you can connect, you need to ensure the network is efficient and the perimeter is secure.
- **[IP Versions](ip-versions.md)**: Understanding IPv4 vs. IPv6.
- **[Firewalls](firewalls.md)**: Setting up allow-lists and security groups.
- **[VPN](vpn.md)**: Basics of secure tunneling and split-tunneling.
- **[UVA VPN](uva-vpn.md)** & **[LUC VPN](luc-vpn.md)**: Institutional examples of VPN implementation.
- **[Mesh Networks](mesh-networks.md)**: Decentralized physical networking and local connectivity.

### Phase 3: Internal Security & Identity
Now that the perimeter is secure, we focus on the "Zero Trust" model inside the VM.
- **[Risks](risks.md)**: Identifying common cloud security pitfalls.
- **[SSH Keys](ssh-keys.md)**: Mastering asymmetric authentication and scope limitation.
- **[Keyring](keyring.md)**: Using OS-native secret storage.
- **[Hardening](hardening.md)**: OS lockdown, `fail2ban`, and compliance benchmarks.
- **[IAM](iam.md)**: Moving from static keys to Cloud Identities and Roles.

### Phase 4: Operations & Maintenance
Learn how to keep your VMs healthy, updated, and efficient.
- **[Monitoring](monitoring.md)**: Using CLI tools and cloud metrics for observability.
- **[Storage](storage.md)**: Managing block, file, and object storage.
- **[Automation](automation.md)**: Infrastructure as Code, `cloud-init`, and Ansible.
- **[Optimization](optimization.md)**: Kernel tuning and HPC performance optimization.

### Phase 5: Advanced Architectures
Final step: scaling your applications and moving toward cloud-native orchestration.
- **[Containers on VMs](containers-on-vms.md)**: Bridging the gap between VMs and Docker/K3s.
- **[Service Mesh](service-mesh.md)**: Managing microservice communication in Kubernetes.
- **[Availability](availability.md)**: Implementing High Availability (HA) and Disaster Recovery (DR).

## How to Use These Guides
Each chapter is designed to be a standalone reference, but the concepts build upon each other. We recommend starting with **Phase 1** and using the **Summary Checklists** at the end of each document to verify your progress.