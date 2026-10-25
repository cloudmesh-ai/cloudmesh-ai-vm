# VM Operations: Snapshots, Resources, and Hardening

Once you have automated the deployment of your VMs, the next step is managing their lifecycle and security. In a professional lab environment, you don't just "launch and forget"—you manage the stability, performance, and security of your infrastructure.

## 1. Snapshots and Recovery

Snapshots allow you to capture the entire state of a VM (disk and configuration) at a specific point in time. This is invaluable when testing risky configuration changes or building a "Golden Image."

### Creating a Snapshot
Before performing a dangerous operation (like upgrading the kernel or changing a system-wide config), take a snapshot:
```bash
multipass snapshot my-ubuntu-vm
```
Multipass will create a point-in-time recovery image.

### Listing and Restoring
If a configuration change breaks your system, you can roll back instantly.

**List available snapshots:**
```bash
multipass snapshots my-ubuntu-vm
```

**Restore a snapshot:**
```bash
multipass restore my-ubuntu-vm
```

### The "Golden Image" Workflow
Instead of running a 10-minute Ansible playbook every time you start a new project:
1. Launch a VM.
2. Run your base Ansible playbook (install Python, Git, MkDocs, etc.).
3. Take a snapshot called `base-ready`.
4. For every new experiment, restore from `base-ready` instead of starting from a clean Ubuntu image.

---

## 2. Resource Tuning

By default, Multipass assigns a generic amount of resources to each VM. For complex clusters (like Kubernetes), you may need to specify exactly how much power each node has.

### Customizing at Launch
You can control the CPU, Memory, and Disk during the `launch` command:

```bash
multipass launch --name heavy-node \
  --cpus 4 \
  --memory 8G \
  --disk 40G
```

**Resource Guide:**
- **`--cpus`**: Number of virtual CPUs. Useful for simulating high-load servers.
- **`--memory`**: Total RAM (e.g., `2G`, `512M`). Critical for memory-intensive apps like Java or Elasticsearch.
- **`--disk`**: Storage size in GB.

### Simulating Hardware Profiles
To test how your application behaves on different hardware, you can create a "Heterogeneous Cluster":
- **Controller Node**: 2 CPUs, 4GB RAM.
- **Worker Node 1 (Light)**: 1 CPU, 1GB RAM.
- **Worker Node 2 (Heavy)**: 4 CPUs, 8GB RAM.

---

## 3. Security Hardening

Even in a local lab, practicing security is essential. If you are running a cluster of VMs, you should control how they communicate.

### Firewall Management with `ufw`
Ubuntu comes with the Uncomplicated Firewall (`ufw`). You should use it to ensure that only necessary ports are open.

**Basic Hardening Script (to be run via Ansible or Fabric):**
```bash
# 1. Reset to defaults: Deny all incoming, allow all outgoing
sudo ufw default deny incoming
sudo ufw default allow outgoing

# 2. Allow SSH (Essential for management)
sudo ufw allow ssh

# 3. Allow specific service ports (e.g., MkDocs on 8000)
sudo ufw allow 8000/tcp

# 4. Enable the firewall
sudo ufw enable
```

### SSH Hardening
To prevent unauthorized access (even in a lab), you should disable password-based logins and rely solely on SSH keys.

**Modify `/etc/ssh/sshd_config`:**
```bash
# Disable password authentication
sudo sed -i 's/PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config

# Disable root login via SSH
sudo sed -i 's/PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config

# Restart SSH to apply changes
sudo systemctl restart ssh
```

---

## Summary Checklist for Lab Operations

| Action | Tool/Command | Purpose |
| :--- | :--- | :--- |
| **Checkpoint** | `multipass snapshot` | Protect against configuration failure. |
| **Rollback** | `multipass restore` | Return to a known-good state. |
| **Profile** | `--cpus` / `--memory` | Simulate different server tiers. |
| **Isolate** | `ufw allow <port>` | Limit attack surface/traffic. |
| **Secure** | `PasswordAuthentication no` | Enforce key-based identity. |