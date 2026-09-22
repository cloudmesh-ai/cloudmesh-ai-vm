# `cmx vm` Cheat Sheet

A quick reference guide for all available Virtual Machine management commands in the `cmx` CLI.

## Quick Reference Table

| Category | Command | Description | Example |
| :--- | :--- | :--- | :--- |
| **Provider** | `provider get` | Show current default cloud provider | `cmx vm provider get` |
| | `provider set <cloud>` | Change default cloud provider | `cmx vm provider set multipass` |
| **Lifecycle** | `start [name]` | Start a new VM (auto-named if name omitted) | `cmx vm start my-vm` |
| | `stop [name]` | Stop a running VM | `cmx vm stop` |
| | `restart [name]` | Reboot a VM | `cmx vm restart` |
| | `suspend [name]` | Suspend VM to disk (if supported) | `cmx vm suspend` |
| | `delete [name]` | Permanently remove a VM | `cmx vm delete` |
| | `reset` | Reset VM or restart provider daemon | `cmx vm reset` |
| | `login [name]` | Get connection info or log into VM | `cmx vm login` |
| **Discovery** | `list` | List all VMs for the active provider | `cmx vm list` |
| | `image` | List available VM images | `cmx vm image` |
| | `flavor` | List available hardware profiles | `cmx vm flavor` |
| | `key list` | List available SSH keys | `cmx vm key list` |
| | `security-groups` | List available security groups | `cmx vm security-groups` |
| **SSH/Net** | `run [name] "cmd"` | Run a command on the VM via SSH | `cmx vm run "hostname"` |
| | `ssh-config [name]` | Generate SSH config for `~/.ssh/config` | `cmx vm ssh-config` |
| | `key upload <path>` | Upload a public key to the cloud | `cmx vm key upload ~/.ssh/id_rsa.pub` |
| | `key delete <name>` | Delete an SSH key from the cloud | `cmx vm key delete my-key` |
| **System** | `account` | View account usage and quotas | `cmx vm account` |
| | `horizon` | Open the OpenStack Horizon dashboard | `cmx vm horizon` |
| **Special** | `reservation` | Create a hardware reservation (Chameleon) | `cmx vm reservation --name lease1 ...` |

## 💡 Pro Tips

### 1. Contextual Memory
Most lifecycle commands (`stop`, `delete`, `restart`, `login`) remember the last VM you started. If you omit the `[name]`, the tool automatically targets that VM.

### 2. Cloud Overrides
You don't need to change your default provider to run a command on another cloud. Use the `--cloud` flag:
```bash
cmx vm start --cloud aws
```

### 3. Interactive Mode
Tired of typing `cmx vm`? Enter the interactive shell:
```bash
cmx vm -i
```

### 4. Output Formats
The `list` command supports multiple output formats for scripting and automation:
- `--table` (Default)
- `--json`
- `--yaml`
- `--csv`
