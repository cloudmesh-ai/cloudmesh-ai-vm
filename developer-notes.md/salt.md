# Introduction to SaltStack

SaltStack (or simply Salt) is a high-speed, Python-based configuration management and orchestration tool. It is designed for massive scalability and extreme speed, utilizing a specialized communication bus based on **ZeroMQ** rather than standard SSH.

## 1. Core Technology Concepts

### Hybrid Architecture (Push and Pull)
Salt typically operates in a Master-Minion architecture. 
- **Salt Master**: The central command center that sends instructions.
- **Salt Minion**: An agent installed on target nodes that executes commands and reports back.

Unlike Puppet (which is strictly pull) or Ansible (which is strictly push), Salt is a hybrid. The Master can push commands to thousands of Minions in seconds, but Minions can also be configured to pull their own states periodically.

### Event-Driven Automation
One of Salt's most powerful features is its **Event Bus**. Salt can monitor for specific events (e.g., a service crashing) and automatically trigger a "Reactor" to fix the problem in real-time without human intervention.

### Declarative State System
Salt uses **States** (written in YAML) to define the desired configuration of a system. These files are called **SLS** (SaLt State) files.

### Key Components
- **Grains**: Static information about a node (e.g., OS, CPU, RAM). Grains are collected by the Minion and available to the Master.
- **Pillars**: Sensitive or node-specific data (e.g., passwords, API keys) stored on the Master and pushed only to the authorized Minion.
- **Salt-Call**: A CLI tool that allows you to run Salt commands locally on a node, enabling "Masterless" mode.

---

## 2. Hands-on Example: Deploying an MkDocs Site

To keep this lab simple, we will use **Masterless Salt**. This means we install the Salt Minion on the VM and use `salt-call` to apply configurations locally without needing a Salt Master.

### The State File (`mkdocs.sls`)

```yaml
install_python:
  pkg.installed:
    - pkgs:
      - python3
      - python3-pip

install_mkdocs:
  pip.installed:
    - name: mkdocs
    - require:
      - pkg: install_python

create_docs_dir:
  file.directory:
    - name: /home/ubuntu/my-docs
    - user: ubuntu
    - group: ubuntu
    - mode: 755

init_mkdocs:
  cmd.run:
    - name: mkdocs new .
    - cwd: /home/ubuntu/my-docs
    - runas: ubuntu
    - creates: /home/ubuntu/my-docs/mkdocs.yml
    - require:
      - file: create_docs_dir

start_mkdocs:
  cmd.run:
    - name: nohup mkdocs serve -a 0.0.0.0:8000 > /dev/null 2>&1 &
    - cwd: /home/ubuntu/my-docs
    - runas: ubuntu
    - unless: pgrep -f "mkdocs serve"
    - require:
      - cmd: init_mkdocs
```

### How to Run and Test

#### 1. Provision the VM
Launch a Multipass VM:
```bash
multipass launch --name salt-vm
```

#### 2. Apply the State
Since we are using Masterless Salt, we will install the Salt minion and execute the state locally.

**Copy the state file to the VM:**
```bash
multipass transfer mkdocs.sls salt-vm:/tmp/mkdocs.sls
```

**Run Salt-Call:**
```bash
multipass exec salt-vm -- sudo bash -c "apt-get update && apt-get install -y salt-minion && salt-call --local state.apply /tmp/mkdocs.sls"
```

#### 3. Verify the Deployment
**Find the IP:**
```bash
multipass list
```

**Test in Browser:**
Navigate to `http://<VM_IP>:8000`. You should see the MkDocs welcome page.

### Summary of Workflow
| Step | Salt Concept | Action |
| :--- | :--- | :--- |
| **Configuration** | State (`.sls`) | Defines the desired state of packages and services in YAML. |
| **Intelligence** | Grains | Used internally by Salt to ensure the right packages are installed for the OS. |
| **Execution** | `salt-call --local` | Bypasses the Master and applies the state directly on the node. |
| **Verification** | HTTP Request | Confirms the service is running on port 8000. |

### Automation with Makefile

To simplify the process of deploying and testing, you can use a `Makefile`. This allows you to trigger the entire workflow with a single command.

Create a file named `Makefile` in your project directory:

```makefile
VM_NAME=salt-vm
STATE_FILE=mkdocs.sls
PORT=8000

.PHONY: vm test clean

# Provision VM, transfer state and apply configuration
vm:
	multipass launch --name $(VM_NAME) || true
	multipass transfer $(STATE_FILE) $(VM_NAME):/tmp/$(STATE_FILE)
	multipass exec $(VM_NAME) -- sudo bash -c "apt-get update && apt-get install -y salt-minion && salt-call --local state.apply /tmp/$(STATE_FILE)"

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
