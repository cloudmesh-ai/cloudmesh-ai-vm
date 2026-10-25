# OS Hardening and Compliance for Cloud VMs

This chapter focuses on reducing the "attack surface" of your virtual machines. While cloud firewalls protect the perimeter, OS hardening ensures that if an attacker manages to penetrate the network, they find it extremely difficult to move laterally or escalate privileges.

## 1. The Attack Surface Concept

The "Attack Surface" is the sum of all points where an unauthorized user can try to enter or extract data from an environment. To harden a VM, you must systematically close every "door" that isn't absolutely necessary for the application to function.

## 2. Securing SSH Access

SSH is the primary gateway to your VM and the most targeted service by bots.

### Disable Root Login
Never allow direct root access via SSH. Instead, log in as a standard user and use `sudo` for administrative tasks.
- **Action**: Edit `/etc/ssh/sshd_config` and set:
  `PermitRootLogin no`

### Enforce Key-Based Authentication
Passwords can be brute-forced. SSH keys cannot. Disable password authentication entirely.
- **Action**: In `/etc/ssh/sshd_config`, set:
  `PasswordAuthentication no`
  `ChallengeResponseAuthentication no`

### Change the Default Port (Security by Obscurity)
While not a primary security measure, changing the SSH port from 22 to a high port (e.g., 2222) eliminates 99% of automated bot noise in your logs.

## 3. Intrusion Prevention and Detection

### fail2ban: Automating the Ban-hammer
`fail2ban` monitors your logs (like `/var/log/auth.log`) for repeated failed login attempts. When it detects a brute-force attack, it automatically adds the attacker's IP to the firewall's drop list.
- **Example**: If an IP fails to login 5 times in 10 minutes, `fail2ban` blocks them for 24 hours.

### host-level Firewalls (UFW/iptables)
Even with a cloud security group, a local firewall provides a second layer of defense.
- **UFW (Uncomplicated Firewall)**: A simple way to manage `iptables`.
- **Command**: `sudo ufw default deny incoming` followed by `sudo ufw allow 22/tcp`.

## 4. Audit and Compliance

Professional environments require an audit trail to prove that security policies are being followed.

### auditd: The System Recorder
The `auditd` daemon tracks security-relevant events. You can configure it to alert you whenever:
- A sensitive file (like `/etc/shadow`) is accessed.
- A user executes a specific privileged command.
- A new user is created on the system.

### CIS Benchmarks
The Center for Internet Security (CIS) provides industry-standard "Benchmarks" for hardening Linux. Following these involves hundreds of small checks, such as:
- Ensuring the `/tmp` partition is mounted with `noexec` and `nosuid`.
- Setting strict permissions on the `/etc/passwd` and `/etc/shadow` files.
- Disabling unused filesystems (e.g., `cramfs`, `freevxfs`).

## 5. User and Privilege Management

- **Principle of Least Privilege**: Give users and applications only the permissions they need. If a web server only needs to read `/var/www/html`, do not run it as root.
- **Sudo Restrictions**: Use the `/etc/sudoers` file to limit which commands specific users can run with root privileges.

## Hardening Checklist

| Category | Action | Priority |
| :--- | :--- | :--- |
| **SSH** | Disable Root Login & Password Auth | Critical |
| **Network** | Enable UFW / Local Firewall | High |
| **Prevention**| Install and configure `fail2ban` | High |
| **Auditing** | Install `auditd` and configure rules | Medium |
| **Compliance**| Review against CIS Benchmarks | Medium |
| **Users** | Remove all unused accounts | Low |