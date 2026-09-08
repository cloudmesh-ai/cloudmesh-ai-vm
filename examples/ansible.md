# Introduction to Ansible

Ansible is an open-source automation tool used for configuration management, application deployment, and infrastructure orchestration. Unlike many other automation tools, Ansible is **agentless**, meaning it doesn't require any software to be installed on the nodes it manages. It connects via standard SSH (or WinRM for Windows) and executes tasks using small programs called **modules**.

## 1. Core Technology Concepts

### Agentless Architecture
Most configuration management tools (like Puppet or Chef) require an "agent" to be installed on every target machine. This agent periodically "pulls" configurations from a central server. Ansible uses a **push model**: the control machine (your laptop) pushes configurations to the target nodes over SSH. This reduces overhead and simplifies security.

### Idempotency
One of the most critical concepts in Ansible is **idempotency**. An idempotent operation is one that has no additional effect if it is called more than once with the same input parameters. 
- **Non-idempotent**: "Add a line to this file." (Running this 5 times adds 5 lines).
- **Idempotent**: "Ensure this line exists in this file." (Running this 5 times results in exactly one line).

Ansible modules are designed to be idempotent, ensuring that your infrastructure stays in the desired state without creating duplicate configurations.

### Key Components
- **Inventory**: A file (INI or YAML) that lists the hosts and groups of hosts that Ansible will manage.
- **Playbooks**: YAML files that describe a series of tasks to be executed on a set of hosts.
- **Modules**: The "building blocks" of Ansible. Modules are specialized tools that perform specific actions (e.g., `apt` for package management, `copy` for moving files, `service` for managing daemons).
- **Tasks**: The smallest unit of action in a playbook, consisting of a single module call.
- **Roles**: A way to bundle playbooks, variables, and files into a reusable structure.

---

## 2. Hands-on Example: Deploying an MkDocs Site

In this example, we will use Ansible to:
1. Launch a Multipass Ubuntu VM.
2. Install Python and the `mkdocs` library.
3. Initialize a simple documentation site.
4. Start the mkdocs web server on port 8000.

### The Playbook (`deploy_docs.yml`)

```yaml
---
- name: Setup MkDocs Web Service
  hosts: localhost
  gather_facts: no
  tasks:
    - name: Launch a Multipass VM
      shell: "multipass launch --name mkdocs-vm"
      register: vm_launch
      ignore_errors: yes # Ignore if VM already exists

    - name: Get VM IP address
      shell: "multipass info mkdocs-vm | grep IPv4 | awk '{print $2}'"
      register: vm_ip

    - name: Add VM to temporary inventory
      add_host:
        name: "mkdocs-vm"
        ansible_host: "{{ vm_ip.stdout }}"
        ansible_user: "ubuntu"

- name: Configure MkDocs on VM
  hosts: mkdocs-vm
  become: true
  tasks:
    - name: Install Python and Pip
      apt:
        name: 
          - python3
          - python3-pip
        state: present
        update_cache: yes

    - name: Install MkDocs via pip
      pip:
        name: mkdocs
        executable: pip3

    - name: Create documentation directory
      file:
        path: /home/ubuntu/my-docs
        state: directory
        owner: ubuntu

    - name: Initialize MkDocs project
      shell: "mkdocs new my-docs"
      args:
        chdir: /home/ubuntu
      become_user: ubuntu

    - name: Start MkDocs server on port 8000
      shell: "nohup mkdocs serve -a 0.0.0.0:8000 > /dev/null 2>&1 &"
      args:
        chdir: /home/ubuntu/my-docs
      become_user: ubuntu
```

### How to Run and Test

#### 1. Prerequisites
Ensure you have Ansible and Multipass installed on your local machine:
```bash
# Install Ansible (Example for macOS/Linux)
pip install ansible
```

#### 2. Execute the Playbook
Run the playbook using the `ansible-playbook` command. Since the first part of our playbook targets `localhost` to create the VM, we can run it without a separate inventory file:

```bash
ansible-playbook deploy_docs.yml
```

#### 3. Verify the Deployment
Once the playbook completes successfully, you can test the web service using the VM's IP address.

**Find the IP:**
```bash
multipass list
```

**Test with Curl:**
If the IP is `192.168.64.5`, run:
```bash
curl http://192.168.64.5:8000
```

**Test in Browser:**
Open your web browser and navigate to `http://<VM_IP>:8000`. You should see the default "Welcome to MkDocs" page.

### Summary of Workflow
| Step | Ansible Component | Action |
| :--- | :--- | :--- |
| **Provisioning** | `shell` module (local) | Calls Multipass to create the Ubuntu VM. |
| **Dynamic Inventory** | `add_host` module | Adds the newly created VM IP to Ansible's memory. |
| **Configuration** | `apt` & `pip` modules | Installs the necessary software stack. |
| **Deployment** | `shell` module (remote) | Initializes the project and starts the web server. |

### Automation with Makefile

To simplify the process of deploying and testing, you can use a `Makefile`. This allows you to trigger the entire workflow with a single command.

Create a file named `Makefile` in your project directory:

```makefile
VM_NAME=mkdocs-vm
PLAYBOOK=deploy_docs.yml
PORT=8000

.PHONY: vm test clean

# Provision VM and apply configuration
vm:
	ansible-playbook $(PLAYBOOK)

# Test if the web service is responding
test:
	@echo "Testing web service at $$(multipass info $(VM_NAME) | grep IPv4 | awk '{print $$2}'):$(PORT)"
	@curl -s http://$$(multipass info $(VM_NAME) | grep IPv4 | awk '{print $$2}'):$(PORT) | grep -q "Welcome" && echo "✅ Test Passed" || echo "❌ Test Failed"

# Cleanup
clean:
	multipass delete $(VM_NAME)
	multipass purge
```

**Usage:**
- Run `make vm` to launch and configure the site.
- Run `make test` to verify the deployment.
- Run `make clean` to remove the VM.
