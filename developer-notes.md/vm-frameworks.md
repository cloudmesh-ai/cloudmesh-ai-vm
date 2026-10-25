# Local VM Frameworks and Hypervisors

Before deploying to the cloud, developers often use local virtualization to build and test images. This chapter compares the frameworks available for starting virtual machines locally across different host operating systems.

## 1. Understanding Hypervisors

A hypervisor is the software that creates and runs virtual machines. There are two main types:
- **Type 1 (Bare Metal)**: Runs directly on the hardware (e.g., Hyper-V, ESXi, KVM). These offer the best performance.
- **Type 2 (Hosted)**: Runs as an application on top of an existing OS (e.g., VirtualBox, VMware Workstation). These are easier to install and use for development.

## 2. Local Frameworks by OS

### Linux
Linux has the most robust local virtualization ecosystem.
- **KVM/QEMU**: The gold standard for Linux. KVM turns the Linux kernel into a Type 1 hypervisor.
- **VirtualBox**: Excellent for cross-platform compatibility and ease of use.
- **VMware Workstation**: Powerful, industry-standard tool for professional VM management.

### Windows
Windows users have a mix of native and third-party options.
- **Hyper-V**: Built into Windows Pro/Enterprise. It is a Type 1 hypervisor and highly efficient.
- **VirtualBox**: The go-to free option for running Linux guests on Windows.
- **VMware Workstation Player/Pro**: High performance and great for complex virtual networking.

### macOS
Apple's transition to Silicon (M1/M2/M3) has changed the local VM landscape.
- **Apple Virtualization Framework**: The native API for macOS.
- **UTM**: A popular open-source GUI for QEMU/Apple Virtualization; excellent for running Linux and Windows on ARM Macs.
- **VMware Fusion / Parallels Desktop**: The most polished "commercial" experiences for running Windows on Mac.

### Raspberry Pi OS (ARM)
Running VMs on a Raspberry Pi is different because it is an ARM-based system with limited resources.
- **QEMU**: Used primarily for *emulating* other architectures (like x86) on the Pi, though it is slow.
- **KVM**: Supported on some Raspberry Pi kernels for ARM-on-ARM virtualization.
- **Containerization (Alternative)**: Because full VMs are heavy, most Pi users use **Docker** or **LXD** for isolation instead of full VMs.

## 3. Framework Comparison Matrix

| Framework | Primary Host OS | Hypervisor Type | Cost | Ease of Use | Performance |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **KVM/QEMU** | Linux | Type 1 | Free | Medium | Very High |
| **Hyper-V** | Windows | Type 1 | Free (Pro) | Medium | High |
| **VirtualBox** | All | Type 2 | Free | High | Medium |
| **VMware** | All | Type 2 | Paid/Free | High | High |
| **UTM** | macOS | Mixed | Free/Paid | High | Medium/High |
| **Parallels** | macOS | Type 2 | Paid | Very High | Very High |

## 4. Official Resources

- **VirtualBox**: [virtualbox.org](https://www.virtualbox.org/)
- **VMware**: [vmware.com](https://www.vmware.com/)
- **UTM (macOS)**: [getutm.app](https://getutm.app/)
- **KVM/QEMU**: [qemu.org](https://www.qemu.org/)

## 5. Choosing the Right Tool

- **For Maximum Performance**: Use the native Type 1 hypervisor for your OS (KVM for Linux, Hyper-V for Windows, Virtualization Framework for Mac).
- **For Rapid Prototyping**: Use **VirtualBox** or **UTM**; they provide the easiest "Import Appliance" experience.
- **For Cross-Architecture Testing**: Use **QEMU**, as it can emulate different CPU architectures (e.g., running ARM on x86).

## Summary Checklist
- [ ] Identify your host OS and hardware architecture (x86 vs ARM).
- [ ] Determine if you need a Type 1 (Performance) or Type 2 (Convenience) hypervisor.
- [ ] Install the framework and verify hardware acceleration (VT-x/AMD-V) is enabled in BIOS/UEFI.
- [ ] Test a basic Linux image to verify network and disk connectivity.