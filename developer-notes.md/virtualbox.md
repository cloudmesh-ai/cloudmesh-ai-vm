# Oracle VM VirtualBox: Comprehensive Guide

VirtualBox is one of the most popular cross-platform Type 2 hypervisors. This guide covers everything from installation to advanced command-line management.

## 1. Installation

### Windows
1. Download the Windows host installer from [virtualbox.org](https://www.virtualbox.org/wiki/Downloads).
2. Run the `.exe` installer and follow the prompts.
3. **Important**: Install the **VirtualBox Extension Pack** (from the same download page) to enable support for USB 2.0/3.0 and RDP.
4. Reboot your system if prompted to finalize network driver installation.

### macOS
1. Download the macOS host installer (`.dmg`).
2. Drag the VirtualBox icon to the Applications folder.
3. **Security Permissions**: On modern macOS, you must go to `System Settings` $\rightarrow$ `Privacy & Security` and click **"Allow"** for the Oracle kernel extension.
4. Reboot your Mac to apply the kernel extensions.

### Linux (Ubuntu/Debian)
While you can download the `.deb` package, using the package manager is recommended:
```bash
sudo apt update
sudo apt install virtualbox
# Install the guest additions ISO for better performance inside the VM
sudo apt install virtualbox-guest-additions-iso
```

## 2. Starting a VM via the GUI

The Graphical User Interface is the easiest way to configure a VM for the first time.

1. **Create**: Click **"New"**. Give your VM a name and select the OS type (e.g., Ubuntu 64-bit).
2. **Resource Allocation**:
   - **Memory**: Assign at least 2GB (2048 MB) for most Linux distros.
   - **Processors**: Assign at least 2 CPUs to avoid sluggishness.
3. **Hard Disk**: Choose "Create a virtual hard disk now" (dynamically allocated is usually best to save host space).
4. **Boot Image**: Go to `Settings` $\rightarrow$ `Storage` $\rightarrow$ `Controller: IDE` $\rightarrow$ Click the empty disk icon and select your `.iso` file.
5. **Network**: Go to `Settings` $\rightarrow$ `Network`. Set "Attached to" to **Bridged Adapter** if you want the VM to be visible to other devices on your network.
6. **Start**: Click the green **"Start"** arrow.

## 3. Starting a VM via Command Line (`VBoxManage`)

For automation and remote management, VirtualBox provides a powerful CLI tool called `VBoxManage`.

### Basic Commands
- **List all VMs**:
  ```bash
  VBoxManage list vms
  ```
- **Start a VM (GUI mode)**:
  ```bash
  VBoxManage startvm "VM Name"
  ```
- **Start a VM (Headless mode)**: Use this to run the VM in the background without a window.
  ```bash
  VBoxManage startvm "VM Name" --type headless
  ```
- **Stop a VM (Power off)**:
  ```bash
  VBoxManage controlvm "VM Name" poweroff
  ```
- **Save State (Pause)**:
  ```bash
  VBoxManage controlvm "VM Name" savestate
  ```

## 4. Accessing the VM via Command Line (Windows Git Bash)

If you are on Windows and have installed **Git Bash**, you can access your Linux VM via SSH, which is much more efficient than using the VirtualBox GUI window.

### Step 1: Get the VM IP Address
Inside the VM terminal, run:
```bash
ip addr show
```
Look for the `inet` address (e.g., `192.168.1.15`).

### Step 2: SSH from Git Bash
Open your Git Bash terminal on Windows and run:
```bash
ssh username@192.168.1.15
```
*(Replace `username` with your VM user and the IP with the one found in Step 1).*

### Troubleshooting Connection Issues
If you cannot connect via SSH:
1. **Check Network Mode**: Ensure the VM is set to **Bridged Adapter** or **Host-Only Adapter**. (NAT mode requires "Port Forwarding" to work).
2. **Check SSH Service**: Ensure the SSH server is running inside the VM:
   ```bash
   sudo systemctl status ssh
   # If not running:
   sudo apt install openssh-server
   sudo systemctl enable --now ssh
   ```
3. **Firewall**: Ensure the VM firewall allows port 22:
   ```bash
   sudo ufw allow 22/tcp
   ```

## Summary Checklist
- [ ] Install VirtualBox and the Extension Pack.
- [ ] Enable Virtualization (VT-x/AMD-V) in your computer's BIOS.
- [ ] Configure a VM with a Bridged Adapter for easy network access.
- [ ] Practice starting the VM in `headless` mode using `VBoxManage`.
- [ ] Successfully SSH into the VM from your host's terminal.