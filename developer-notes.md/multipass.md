# Multipass: Lightweight Ubuntu VMs

Multipass is a lightweight VM manager created by Canonical. It allows developers to spin up Ubuntu instances in seconds, making it an ideal bridge between local development and cloud deployment.

## 1. Supported Systems

Multipass uses the native hypervisor of the host operating system to ensure high performance.

- **Windows**: Uses **Hyper-V** (native) or **VirtualBox**.
- **macOS**: Uses **Virtualization.framework** (native on Apple Silicon and Intel), **HyperKit**, or **VirtualBox**.
- **Linux**: Uses **KVM** (Kernel-based Virtual Machine).

## 2. Getting Started

### Installation
- **Windows/macOS**: Download the installer from [multipass.run](https://multipass.run/).
- **Linux**: Install via snap:
  ```bash
  sudo snap install multipass
  ```

### Basic Lifecycle Management
Multipass simplifies VM management into a few intuitive commands and fully supports running multiple concurrent VMs.

- **Launch a VM**: Creates and starts a new Ubuntu instance.
  ```bash
  multipass launch --name vm-1
  multipass launch --name vm-2
  ```
- **List VMs**: Check the status and IP addresses of your instances.
  ```bash
  multipass list
  ```
- **List VMs**: Check the status and IP addresses of your instances.
  ```bash
  multipass list
  ```
- **Stop a VM**:
  ```bash
  multipass stop my-ubuntu
  ```
- **Delete a VM**:
  ```bash
  multipass delete my-ubuntu
  multipass purge  # Permanently removes deleted VMs
  ```

## 3. Accessing and Connecting VMs

Multipass provides two primary ways to interact with your instances, and because all Multipass VMs share a virtual network, they can communicate with each other.

### Accessing a VM from the Host
Multipass provides two primary ways to interact with your instance.

### Method 1: The Native Shell (The Fast Way)
You can enter the VM immediately without needing to manage SSH keys or IP addresses.
```bash
multipass shell my-ubuntu
```

### Method 2: Standard SSH (The Professional Way)
For a more realistic cloud experience, you can use a standard SSH client from your host terminal (e.g., Git Bash on Windows or Terminal on Mac/Linux).

1. **Find the IP address**:
   ```bash
   multipass list
   ```
   *(Example output: `my-ubuntu  Running  192.168.64.5`)*

2. **Connect via SSH**:
   Multipass automatically adds the VM's public key to your host. You can connect using:
   ```bash
   ssh ubuntu@192.168.64.5
   ```

### Inter-VM Communication (VM-to-VM SSH)

To allow one VM (e.g., `vm-1`) to log into another (`vm-2`) without a password, you must set up SSH keys between them.

**Step 1: Generate a key on `vm-1`**
Log into `vm-1` and create an SSH key pair:
```bash
multipass shell vm-1
ssh-keygen -t rsa -b 4096 -N "" -f ~/.ssh/id_rsa
```

**Step 2: Copy the key to `vm-2`**
You need to get the public key from `vm-1` into the `authorized_keys` file of `vm-2`.
1. Get the public key content from `vm-1`:
   ```bash
   cat ~/.ssh/id_rsa.pub
   ```
2. Copy that text, exit `vm-1`, and enter `vm-2`:
   ```bash
   exit
   multipass shell vm-2
   ```
3. Append the key to the authorized list:
   ```bash
   echo "PASTE_PUBLIC_KEY_HERE" >> ~/.ssh/authorized_keys
   chmod 600 ~/.ssh/authorized_keys
   ```

**Step 3: Test the connection**
Now, from `vm-1`, you can SSH into `vm-2` using its IP (found via `multipass list`):
```bash
# Inside vm-1
ssh ubuntu@192.168.64.x
```

## 4. Multipass vs. VirtualBox

| Feature | Multipass | VirtualBox |
| :--- | :--- | :--- |
| **Setup Time** | Seconds | Minutes |
| **Interface** | CLI-first | GUI-first |
| **OS Support** | Ubuntu Only | Almost any OS |
| **Resources** | Very Lightweight | Heavier |
| **Control** | High-level abstraction | Low-level hardware control |

**Use Multipass when**: You need a quick, clean Ubuntu environment to test a script or a small app.
**Use VirtualBox when**: You need a specific non-Ubuntu OS, complex virtual networking, or a full GUI desktop for the guest VM.

## 5. Automating Multi-VM Clusters with Python

If you need to spin up a cluster of `n` VMs for testing a distributed system, doing it manually is tedious. You can use Python's `subprocess` module to automate the creation and the "full-mesh" SSH key distribution.

### Automated Cluster Script
The following script creates `n` VMs and ensures that every VM can SSH into every other VM without a password.

```python
import subprocess
import time
import re

def run_cmd(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout.strip()

def setup_cluster(n=3):
    vms = [f"node-{i}" for i in range(1, n + 1)]
    print(f"🚀 Provisioning and starting {n} VMs...")
    
    for vm in vms:
        # Launch creates and starts, but we explicitly call start to ensure it's active
        run_cmd(f"multipass launch --name {vm}")
        run_cmd(f"multipass start {vm}")

    print("⏳ Waiting for VMs to initialize network...")
    time.sleep(10) # Ensure SSH and network are ready

    # Map VM names to IPs
    ip_map = {}
    list_output = run_cmd("multipass list")
    for line in list_output.splitlines()[1:]:
        parts = re.split(r'\s+', line.strip())
        if len(parts) >= 3:
            ip_map[parts[0]] = parts[-1]

    print("🌐 IP Mapping:", ip_map)

    # Setup Full-Mesh SSH Keys
    for source_vm in vms:
        print(f"🔑 Configuring keys for {source_vm}...")
        
        # 1. Generate key on source
        run_cmd(f"multipass exec {source_vm} -- bash -c 'ssh-keygen -t rsa -N \"\" -f ~/.ssh/id_rsa'")
        pub_key = run_cmd(f"multipass exec {source_vm} -- cat ~/.ssh/id_rsa.pub")

        # 2. Distribute key to all other VMs
        for dest_vm in vms:
            if source_vm == dest_vm: continue
            dest_ip = ip_map[dest_vm]
            # Append public key to authorized_keys of destination
            run_cmd(f"multipass exec {dest_vm} -- bash -c 'echo \"{pub_key}\" >> ~/.ssh/authorized_keys'")

    print("\n✅ Cluster Ready! All nodes can SSH into each other.")
    print("Try it: multipass shell node-1 && ssh ubuntu@<node-2-ip>")

if __name__ == "__main__":
    setup_cluster(3) # Change 3 to your desired number of VMs
```

### How this works:
1. **Provisioning**: It uses `multipass launch` to create named instances.
2. **Discovery**: It parses `multipass list` to build a mapping of VM names to internal IP addresses.
3. **Key Generation**: It uses `multipass exec` to run `ssh-keygen` inside each VM.
4. **Distribution**: It reads the public key from the source and appends it to the `~/.ssh/authorized_keys` file of every other VM in the cluster.
5. **Host Access**: Since Multipass manages the host's key automatically, you can still use `multipass shell <name>` or `ssh ubuntu@<ip>` from your host.

## 6. Enterprise Configuration Management

While a Python script is great for initial bootstrapping, professional environments use Configuration Management (CM) tools to maintain the state of a cluster. 

**Important Distinction: Provisioning vs. Configuration**
CM tools like Ansible, Puppet, Chef, and Salt are designed to configure *existing* systems. They do **not** include the `multipass launch` command. You must first provision your VMs (using the Python script in Section 5 or the Multipass CLI) so that they have an IP address and an SSH server running. Once the VMs are "alive," these tools are used to manage their internal state.

### The "Extended Workflow": Orchestrated Deployment
To avoid manual steps, professional DevOps engineers use an **Orchestrator** (like a Python wrapper or Jenkins pipeline) to chain the launch and configuration together.

**Example: The "Provision-to-Configure" Pipeline**
Instead of running a playbook manually, you use a script that:
1. **Provision**: Calls `multipass launch` to create the nodes.
2. **Discover**: Runs `multipass list` to capture the dynamic IP addresses.
3. **Inventory**: Writes those IPs into an Ansible `inventory.ini` file.
4. **Configure**: Executes `ansible-playbook` to apply the final state.

**Conceptual Python Orchestrator Snippet**:
```python
# 1. Provision
subprocess.run("multipass launch --name node-1", shell=True)

# 2. Discover IP
ip = subprocess.run("multipass info node-1 | grep IPv4", shell=True, capture_output=True).stdout

# 3. Generate Inventory
with open("inventory.ini", "w") as f:
    f.write(f"[cluster]\nnode-1 {ip}")

# 4. Configure
subprocess.run("ansible-playbook -i inventory.ini site.yml", shell=True)
```

Here is how you would implement a "full-mesh" SSH trust using the four major CM frameworks once the VMs are launched.

### Ansible (Agentless/Push)
Ansible is the most popular choice for this because it uses SSH. It can easily loop through a list of hosts and push keys.
```yaml
# playbook.yml
- hosts: all
  gather_facts: yes
  tasks:
    - name: Ensure SSH key is present on all nodes
      ansible.posix.authorized_key:
        user: ubuntu
        state: present
        key: "{{ lookup('file', '~/.ssh/id_rsa.pub') }}"
```
*Run with: `ansible-playbook -i inventory.ini playbook.yml`*

### Puppet (Agent-based/Pull)
Puppet uses a declarative language to ensure the state is maintained. You would typically define the keys in a manifest.
```puppet
# ssh_trust.pp
$nodes_keys = {
  'node-1' => 'ssh-rsa AAAAB3...',
  'node-2' => 'ssh-rsa AAAAB3...',
}

$nodes_keys.each |$name, $key| {
  ssh_authorized_key { $name:
    ensure => present,
    user   => 'ubuntu',
    type   => 'ssh-rsa',
    key    => $key,
  }
}
```

### Chef (Agent-based/Pull)
Chef uses "recipes" written in Ruby to manage resources.
```ruby
# recipe_ssh.rb
node['cluster_nodes'].each do |node_name, pub_key|
  directory '/home/ubuntu/.ssh' do
    mode '0700'
    owner 'ubuntu'
  end

  remote_file "/home/ubuntu/.ssh/authorized_keys" do
    content pub_key
    mode '0600'
    owner 'ubuntu'
    action :create
  end
end
```

### SaltStack (Event-driven/Push-Pull)
Salt is extremely fast and uses a "State" system (SLS) to manage configurations.
```yaml
# ssh_trust.sls
manage_ssh_keys:
  ssh_authorized_keys.present:
    - user: ubuntu
    - keys:
        - ssh-rsa AAAAB3... (node-1)
        - ssh-rsa AAAAB3... (node-2)
```
*Run with: `salt '*' state.apply ssh_trust`*

### Comparison for Cluster Trust

| Tool | Architecture | Strength for this Task | Ideal Use Case |
| :--- | :--- | :--- | :--- |
| **Ansible** | Agentless | Extremely fast to set up | Rapid prototyping, small clusters |
| **Puppet** | Agent-based | Strong state enforcement | Large, stable enterprise fleets |
| **Chef** | Agent-based | Highly flexible (Ruby) | Complex, dynamic configurations |
| **Salt** | Hybrid | Speed and scale | Massive clusters, event-driven infra |

## Summary Checklist
- [ ] Install Multipass from multipass.run.
- [ ] Launch your first instance using `multipass launch`.
- [ ] Enter the VM using `multipass shell`.
- [ ] Practice connecting to the VM using a standard SSH client and the VM's IP.
- [ ] Cleanup your environment using `multipass delete` and `multipass purge`.

## Appendix: Detailed Ansible Lab Setup

If you want to build a local mini-cluster on your laptop, a common professional pattern is to use Ansible to handle the configuration and trust relationships after the VMs are launched.

### The Conceptual Workflow
1. **Provision**: Ansible (via a wrapper script) or the Multipass CLI starts $N$ VMs.
2. **Identify**: Each VM is assigned a known hostname and IP.
3. **Management Access**: Ansible installs your host's public SSH key so you can manage the VMs.
4. **Inter-VM Trust**: A dedicated cluster SSH key is distributed so VMs can talk to each other.
5. **Inventory**: An Ansible inventory is generated from the VM addresses.

### Example Playbook: Cluster Configuration
Assuming the VMs are already launched and you are using their IPs:

```yaml
---
- name: Configure VMs
  hosts: all
  become: true

  vars:
    ssh_public_key: "{{ lookup('file', '~/.ssh/id_ed25519.pub') }}"

  tasks:
    - name: Create admin user
      ansible.builtin.user:
        name: ansible
        groups: sudo
        append: true
        shell: /bin/bash
        create_home: true

    - name: Allow admin user to use sudo without password
      ansible.builtin.copy:
        dest: /etc/sudoers.d/ansible
        content: "ansible ALL=(ALL) NOPASSWD:ALL\n"
        mode: "0440"

    - name: Add your SSH key
      ansible.posix.authorized_key:
        user: ansible
        key: "{{ ssh_public_key }}"

    - name: Install SSH server
      ansible.builtin.apt:
        name: openssh-server
        state: present
        update_cache: true

    - name: Make sure SSH is running
      ansible.builtin.service:
        name: ssh
        state: started
        enabled: true

    - name: Add all VMs to /etc/hosts
      ansible.builtin.lineinfile:
        path: /etc/hosts
        line: "{{ hostvars[item].ansible_host }} {{ item }}"
      loop: "{{ groups['all'] }}"
```

### Sample Inventory (`inventory.ini`)
```ini
[vms]
vm01 ansible_host=10.0.0.11
vm02 ansible_host=10.0.0.12
vm03 ansible_host=10.0.0.13

[vms:vars]
ansible_user=ansible
```

### Implementing VM-to-VM SSH Trust
To avoid copying your personal private key between VMs (a security risk), the best practice is to create a dedicated **cluster key** that only exists on the VMs.

Add these tasks to your playbook:

```yaml
- name: Generate cluster SSH key
  community.crypto.openssh_keypair:
    path: /home/ansible/.ssh/id_ed25519
    type: ed25519
    owner: ansible
    group: ansible
    mode: "0600"

- name: Read cluster public key
  ansible.builtin.slurp:
    src: /home/ansible/.ssh/id_ed25519.pub
  register: cluster_public_key

- name: Allow cluster SSH access
  ansible.posix.authorized_key:
    user: ansible
    key: "{{ hostvars[item].cluster_public_key.content | b64decode }}"
  loop: "{{ groups['all'] }}"
```

With this setup:
- You can log in from your laptop: `ssh ansible@10.0.0.11`
- VMs can log into each other: `ssh ansible@vm02` (from vm01) without a password.
