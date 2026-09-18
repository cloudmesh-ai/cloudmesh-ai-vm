# Introduction to Chef

Chef is a powerful configuration management tool that treats infrastructure as actual code. While tools like Ansible use YAML for simplicity, Chef uses a Ruby-based DSL (Domain Specific Language), providing developers with the full power of a programming language to define their systems.

## 1. Core Technology Concepts

### Client-Server Architecture
Chef typically operates with a **Chef Server** at the center. 
- **Chef Infra Client**: An agent installed on every node. It authenticates with the server, downloads the required "Cookbooks," and applies them locally.
- **Chef Server**: Stores the cookbooks, node metadata, and configuration policies.
- **Chef Workstation**: The machine where developers write and test their cookbooks before uploading them to the server.

### The "Cookbook" Metaphor
Chef organizes its configuration using a culinary metaphor:
- **Resources**: The smallest unit of configuration (e.g., "this package should be installed").
- **Recipes**: A collection of resources that describes a specific configuration (e.g., "How to install and configure MkDocs").
- **Cookbooks**: A package containing recipes, attributes, files, and templates. A cookbook is the primary unit of distribution in Chef.

### Imperative vs. Declarative
Chef is often described as "declarative," but because it is based on Ruby, it allows for an **imperative style**. You can use loops, conditionals, and complex logic directly within your recipes to handle highly dynamic environments.

### Key Components
- **Ohai**: A tool that runs at the start of every Chef client run to collect system attributes (OS, IP, etc.), similar to Facter in Puppet.
- **Attributes**: Variables used to customize the behavior of a cookbook across different environments (e.g., different ports for Dev vs. Prod).
- **Chef Solo**: A mode that allows you to run Chef on a single node without needing a central Chef Server.

---

## 2. Hands-on Example: Deploying an MkDocs Site

Setting up a full Chef Server is a significant undertaking. For this lab, we will use **Chef Solo**, which allows us to run a recipe locally on a VM.

### The Recipe (`deploy_docs.rb`)

```ruby
# Ensure Python and Pip are installed
package 'python3' do
  action :install
end

package 'python3-pip' do
  action :install
end

# Install MkDocs using a shell command
execute 'install_mkdocs' do
  command '/usr/bin/pip3 install mkdocs'
  not_if 'mkdocs --version'
end

# Create the documentation directory
directory '/home/ubuntu/my-docs' do
  owner 'ubuntu'
  group 'ubuntu'
  mode '0755'
  recursive true
end

# Initialize MkDocs project
execute 'init_mkdocs' do
  command 'mkdocs new .'
  cwd '/home/ubuntu/my-docs'
  user 'ubuntu'
  creates '/home/ubuntu/my-docs/mkdocs.yml'
end

# Start MkDocs server on port 8000
execute 'start_mkdocs' do
  command 'nohup mkdocs serve -a 0.0.0.0:8000 > /dev/null 2>&1 &'
  cwd '/home/ubuntu/my-docs'
  user 'ubuntu'
  not_if 'pgrep -f "mkdocs serve"'
end
```

### How to Run and Test

#### 1. Provision the VM
Launch a Multipass VM:
```bash
multipass launch --name chef-vm
```

#### 2. Apply the Recipe
Chef is not installed by default. We will install the Chef Infra Client and run the recipe using the `chef-client` command in local mode.

**Copy the recipe to the VM:**
```bash
multipass transfer deploy_docs.rb chef-vm:/tmp/deploy_docs.rb
```

**Run Chef Client:**
```bash
multipass exec chef-vm -- sudo bash -c "curl -L https://omnitruck.chef.io/install.sh | bash -s -- -P | sudo bash && sudo chef-client -z /tmp/deploy_docs.rb"
```
*(Note: `-z` tells Chef to run in local mode without a server).*

#### 3. Verify the Deployment
**Find the IP:**
```bash
multipass list
```

**Test in Browser:**
Navigate to `http://<VM_IP>:8000`. You should see the MkDocs welcome page.

### Summary of Workflow
| Step | Chef Concept | Action |
| :--- | :--- | :--- |
| **Configuration** | Recipe (`.rb`) | Uses Ruby DSL to define resources and their desired states. |
| **Discovery** | Ohai | Automatically gathers system attributes before the run. |
| **Execution** | `chef-client -z` | Runs the recipe locally on the node without a central server. |
| **Verification** | HTTP Request | Confirms the service is running on port 8000. |

### Automation with Makefile

To simplify the process of deploying and testing, you can use a `Makefile`. This allows you to trigger the entire workflow with a single command.

Create a file named `Makefile` in your project directory:

```makefile
VM_NAME=chef-vm
RECIPE=deploy_docs.rb
PORT=8000

.PHONY: vm test clean

# Provision VM, transfer recipe and apply configuration
vm:
	multipass launch --name $(VM_NAME) || true
	multipass transfer $(RECIPE) $(VM_NAME):/tmp/$(RECIPE)
	multipass exec $(VM_NAME) -- sudo bash -c "curl -L https://omnitruck.chef.io/install.sh | bash -s -- -P | sudo bash && sudo chef-client -z /tmp/$(RECIPE)"

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
