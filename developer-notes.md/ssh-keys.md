# Understanding and Managing SSH Keys

This chapter explains the mechanics of SSH keys, how they differ from traditional passwords, and how to determine whether to use them or a dedicated secret manager like a vault or a system keyring.

## 1. What are SSH Keys?

Secure Shell (SSH) keys use **asymmetric cryptography**. Unlike a password (symmetric), which is a single secret shared between you and the server, SSH keys come in a mathematically linked pair:

### The Public Key (`id_rsa.pub`)
- **What it is**: A non-secret key that you upload to any server you wish to access.
- **Role**: It acts like a "lock." Anyone can see it, but it can only be opened by the corresponding private key.
- **Placement**: Usually placed in the `~/.ssh/authorized_keys` file on the remote server.

### The Private Key (`id_rsa`)
- **What it is**: A highly sensitive secret that stays exclusively on your local machine.
- **Role**: It acts like the "physical key." It is used to prove your identity to the server.
- **Placement**: Stored in `~/.ssh/` with strict permissions (`chmod 600`).

**The Handshake**: When you connect, the server sends a challenge encrypted with your public key. Only the holder of the matching private key can decrypt the challenge and prove their identity.

## 2. SSH Key Management Best Practices

Using SSH keys without proper management can be as risky as using passwords.

- **Always Use a Passphrase**: Encrypt your private key with a passphrase. If your laptop is stolen, the attacker cannot use your key without the passphrase.
- **Use an SSH Agent**: To avoid typing your passphrase for every connection, use `ssh-agent`. It stores your decrypted keys in memory for the duration of your session.
- **Rotate Your Keys**: Regularly generate new key pairs and remove old public keys from servers to limit the impact of a potentially leaked private key.
- **One Key per Purpose**: Consider using different keys for different environments (e.g., one for production, one for development).

### The "Passwordless" Key Trap

You may encounter situations where a colleague or a tutorial suggests using **passwordless keys** (creating a key pair without a passphrase) for "convenience" or "automation."

**The Risk**: A passwordless private key is a "bearer token." Anyone who gains access to that file—whether through a stolen laptop, a misconfigured backup, or an accidental Git commit—has **immediate and total access** to every server that trusts that public key. There is no second line of defense.

**What should you do?**
- **For Personal Access**: Refuse to use passwordless keys. Use a strong passphrase and leverage `ssh-agent`. The agent provides the convenience of "passwordless" login after the first authentication of the session, but keeps the key encrypted on disk.
- **For Automation/M2M**: In automated scripts where a human cannot enter a password, passwordless keys are common. However, you must apply extreme hardening:
    1. **Restrict the Key**: Use the `authorized_keys` file on the server to restrict the key to a specific IP address or a specific command (e.g., `command="/usr/bin/backup.sh" ssh-rsa ...`).
    2. **Strict Permissions**: Ensure the key is owned by the service user and set to `chmod 400`.
    3. **Consider Alternatives**: Use short-lived certificates or cloud-native identity roles (like AWS IAM Instance Profiles) that eliminate the need for static private keys entirely.

### Advanced Security: Limiting Key Scope

By default, a public key added to `authorized_keys` grants the user full access to the account's shell and all its permissions. To follow the **Principle of Least Privilege**, you should restrict what a specific key can actually do.

You can do this by adding "options" as a prefix to the key entry in the remote server's `~/.ssh/authorized_keys` file.

#### Common Scope Restrictions

| Option | Purpose | Example | Effect |
| :--- | :--- | :--- | :--- |
| **`from="pattern"`** | IP Restriction | `from="192.168.1.10"` | Key only works if the connection originates from this IP. |
| **`command="cmd"`** | Forced Command | `command="/usr/bin/backup.sh"` | Any connection with this key executes only this script and then exits. |
| **`no-port-forwarding`** | Disable Tunneling | `no-port-forwarding` | Prevents the user from using the server as a proxy/tunnel. |
| **`no-pty`** | Disable Shell | `no-pty` | Prevents the allocation of a pseudo-terminal (stops interactive shells). |
| **`restrict`** | Lockdown | `restrict` | Disables all forwarding, PTY, and agent jumping by default. |

#### Practical Examples

**1. The "Automation Only" Key**
If you have a script that only needs to run a backup, do not give it full shell access. In `~/.ssh/authorized_keys`, use:
```text
command="/home/user/scripts/backup.sh",no-port-forwarding,no-pty,no-agent-forwarding ssh-rsa AAAAB3Nza... user@automation-box
```
*Even if this key is stolen, the attacker can only run the backup script; they cannot get a shell or tunnel into your network.*

**2. The "Office-Only" Admin Key**
Limit your administrative key to only be usable from your company's VPN or office IP:
```text
from="203.0.113.45",from="10.0.5.0/24" ssh-rsa AAAAB3Nza... admin@laptop
```

**3. The "Ultra-Secure" Restricted Key**
Use `restrict` to shut down everything, then explicitly enable only what is needed:
```text
restrict,port-forwarding ssh-rsa AAAAB3Nza... tunnel-user@laptop
```

## 3. SSH Keys vs. Keyrings vs. Vaults

A common point of confusion is when to use an SSH key versus a secret manager. They solve different problems.

### When SSH Keys are the Right Tool
SSH keys are designed for **Authentication and Access**.
- **Server Administration**: Logging into a Linux VM to run commands.
- **Git Authentication**: Pushing code to GitHub/GitLab without typing a password.
- **Machine-to-Machine (M2M)**: Allowing a backup server to securely pull data from a database server.

### When a Keyring is Better
System keyrings are designed for **Local Secret Storage**.
- **API Tokens**: Storing a long-lived AWS or Azure API token used by a local Python script.
- **Application Passwords**: Storing the password for a database that your local app connects to.
- **Developer Convenience**: Avoiding the need to keep `.env` files on your disk.

### When a Vault is Better
Vaults (like HashiCorp Vault or Azure Key Vault) are designed for **Centralized Secret Lifecycle Management**.
- **Dynamic Secrets**: Generating a temporary database password that expires after 1 hour.
- **Centralized Auditing**: Knowing exactly which user or service accessed which secret at what time.
- **CI/CD Pipelines**: Providing secrets to a GitHub Action or Jenkins pipeline without storing them in the repository.
- **Enterprise Scale**: Managing thousands of secrets across hundreds of servers.

## 4. Comparison Matrix

| Feature | SSH Keys | System Keyring | Secret Vault |
| :--- | :--- | :--- | :--- |
| **Primary Purpose** | Access/Identity | Local Storage | Lifecycle Management |
| **Secret Type** | Asymmetric Pair | Symmetric (K/V) | Dynamic & Static |
| **Storage Location** | Local File (`~/.ssh`) | OS Secure Enclave | Centralized Server |
| **Best Use Case** | SSHing into VMs | Local Dev Tokens | Production CI/CD |
| **Management** | Manual/Distributed | User-based | Centralized/API-driven |
| **Risk if Leaked** | Unauthorized Server Access | Local Identity Theft | Total Infrastructure Breach |

## Summary: Decision Flow

1. **Do I need to log into a remote shell or push code to Git?** $\rightarrow$ Use **SSH Keys**.
2. **Do I need to store a token for a tool I run only on my laptop?** $\rightarrow$ Use **System Keyring**.
3. **Do I need a secret for a production app, a CI/CD pipeline, or a shared team environment?** $\rightarrow$ Use a **Vault**.