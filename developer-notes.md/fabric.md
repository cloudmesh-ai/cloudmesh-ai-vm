# Introduction to Fabric

Fabric is a high-level Python library designed to execute shell commands remotely over SSH. While Ansible is built for "State Management" (ensuring a system *is* in a certain state), Fabric is built for "Execution" (doing things to a system). It is an excellent choice for deployment scripts, application restarts, and simple orchestration tasks.

## 1. Core Technology Concepts

### SSH-Based Execution
Fabric leverages the `paramiko` library to establish SSH connections. Unlike agent-based tools (Puppet/Chef), Fabric requires nothing on the remote server except a working SSH daemon and Python (if using certain high-level features).

### Imperative Orchestration
Fabric is **imperative**. You write a Python script that says: "Do A, then do B, then do C." This makes it feel more like a standard Python program and less like a configuration file.

### Key Components
- **Connection**: An object representing the SSH session to a specific host.
- **Tasks**: Python functions that define the actions to be taken on the remote host.
- **Group**: A collection of connections allowing you to run the same task across multiple servers simultaneously.

---

## 2. Hands-on Example: Deploying an MkDocs Site

In this example, we will use Fabric to connect to a Multipass VM, install the necessary software, and launch an MkDocs site.

### The Fabric File (`fabfile.py`)

```python
from fabric import task

# Configuration: Change this to your VM's IP
VM_IP = "192.168.64.5" 
VM_USER = "ubuntu"

@task
def deploy(c):
    """
    Provision and start an MkDocs site on the remote VM.
    """
    print(f"🚀 Connecting to {VM_IP}...")
    
    # 1. Install dependencies
    print("📦 Installing Python and Pip...")
    c.sudo("apt-get update -y")
    c.sudo("apt-get install -y python3 python3-pip")

    # 2. Install MkDocs
    print("📚 Installing MkDocs...")
    c.run("pip3 install mkdocs")

    # 3. Initialize the project
    print("📁 Creating documentation project...")
    c.run("mkdir -p ~/my-docs")
    # Use 'cd' via a single shell call or run inside the directory
    c.run("cd ~/my-docs && mkdocs new .")

    # 4. Start the server
    print("🌐 Starting MkDocs server on port 8000...")
    # Use nohup to keep the process running after the SSH session closes
    c.run("nohup mkdocs serve -a 0.0.0.0:8000 > /dev/null 2>&1 &")
    
    print("\n✅ Deployment Complete!")
    print(f"Visit: http://{VM_IP}:8000")

@task
def status(c):
    """Check if the MkDocs server is running."""
    result = c.run("pgrep -f 'mkdocs serve'", warn=True, hide=True)
    if result.ok:
        print("✅ MkDocs is running.")
    else:
        print("❌ MkDocs is not running.")

@task
def stop(c):
    """Stop the MkDocs server."""
    print("🛑 Stopping MkDocs...")
    c.sudo("pkill -f 'mkdocs serve'")
    print("Done.")
```

### How to Run and Test

#### 1. Install Fabric
Install the Fabric library on your local machine:
```bash
pip install fabric
```

#### 2. Provision the VM
Launch your Multipass VM and get its IP:
```bash
multipass launch --name fabric-vm
multipass list
```
*Update the `VM_IP` in `fabfile.py` with the IP from the list.*

#### 3. Execute the Tasks
Fabric uses the `fab` command-line tool to run functions decorated with `@task`.

**Deploy the site:**
```bash
fab -H ubuntu@<VM_IP> deploy
```

**Check status:**
```bash
fab -H ubuntu@<VM_IP> status
```

**Stop the service:**
```bash
fab -H ubuntu@<VM_IP> stop
```

---

## 3. Fabric vs. Ansible: Which one to choose?

Since both use SSH and Python, it's common to wonder which to use.

| Feature | Fabric | Ansible |
| :--- | :--- | :--- |
| **Philosophy** | Imperative (Do this, then that) | Declarative (Ensure this state) |
| **Learning Curve** | Low (it's just Python) | Medium (YAML DSL + Modules) |
| **Idempotency** | Manual (you must check if a file exists) | Automatic (handled by modules) |
| **Scale** | Small to Medium clusters | Massive enterprise fleets |
| **Best Use Case** | Quick deployments, app restarts, ad-hoc scripts | Infrastructure-as-Code, OS hardening, complex state |

**Rule of Thumb:**
- Use **Fabric** if you want to write a quick Python script to "push a button" and deploy an app.
- Use **Ansible** if you are managing a server's entire lifecycle and want to ensure it never drifts from its configuration.