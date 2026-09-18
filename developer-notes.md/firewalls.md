# Configuring Cloud Firewalls and Security Groups

This chapter explains how to protect your cloud instances using firewalls—specifically "Security Groups" in OpenStack and other cloud environments. The primary goal is to implement a "Default Deny" posture, where only explicitly trusted traffic is allowed.

## 1. Fundamental Concepts

A cloud firewall is a virtualized filter that controls traffic entering (Ingress) and leaving (Egress) your virtual machine.

### Statefulness
Cloud security groups are **stateful**. This means if you allow an inbound request on port 22 (SSH), the firewall automatically allows the response to leave the server, regardless of your outbound rules.

### CIDR Notation

Firewalls use **Classless Inter-Domain Routing (CIDR)** to define IP ranges. CIDR is a method for allocating IP addresses and routing IP packets.

#### How the "Slash" Notation Works
The number following the slash (e.g., `/24`) is called the **prefix length**. It tells the computer how many bits of the 32-bit IP address are "fixed" (the network part) and how many are "variable" (the host part).

- **A larger number** (like `/32`) means more bits are fixed $\rightarrow$ **Smaller range**.
- **A smaller number** (like `/8`) means fewer bits are fixed $\rightarrow$ **Larger range**.

#### Common CIDR Prefixes and Their Sizes

| CIDR | Fixed Bits | Variable Bits | Number of IPs | Scope |
| :--- | :--- | :--- | :--- | :--- |
| **`/32`** | 32 | 0 | 1 | **Single Host**: Exactly one specific IP address. |
| **`/24`** | 24 | 8 | 256 | **Small Network**: A typical home or small office subnet. |
| **`/16`** | 16 | 16 | 65,536 | **Medium Network**: Often used for a university campus or large corp. |
| **`/8`** | 8 | 24 | 16.7 Million | **Huge Network**: Massive internal networks or ISP blocks. |
| **`/0`** | 0 | 32 | 4.2 Billion | **The Whole World**: Every possible IPv4 address. |

#### Practical Examples
- `192.168.1.10/32`: Only allows the device at exactly `.10`.
- `192.168.1.0/24`: Allows any device from `192.168.1.0` to `192.168.1.255`.

## 2. Setting Up an Allow-List Firewall

The most secure way to configure a firewall is to create an **Allow-List**. Instead of trying to block "bad" IPs, you block everything by default and only open ports for trusted networks.

### The Setup Process
1. **Create a Security Group**: A named container for your rules (e.g., `trusted-campus-access`).
2. **Define the Inbound Rule**:
   - **Protocol**: TCP
   - **Port**: 22 (for SSH) or 80/443 (for Web).
   - **Remote IP/CIDR**: The specific range of your organization.
3. **Assign to VM**: Attach the security group to your instance during or after boot.

## 3. Practical Examples: Campus IP Restrictions

In academic and research environments, you often want to ensure that only people on the university network can access your management ports.

### Example 1: Restricting Access to UVA (University of Virginia)
Suppose UVA provides a set of public IP ranges for its campus. To allow only UVA users to SSH into your VM, you would add the following rules to your security group:

| Protocol | Port | Remote CIDR | Description |
| :--- | :--- | :--- | :--- |
| TCP | 22 | `128.142.0.0/16` | UVA Campus Range A (Example) |
| TCP | 22 | `129.215.0.0/16` | UVA Campus Range B (Example) |

**OpenStack CLI Command:**
```bash
openstack security group rule create --protocol tcp --dst-port 22 --remote-ip 128.142.0.0/16 trusted-campus-access
```

### Example 2: Restricting Access to LUC (Loyola University Chicago)
Similarly, for LUC, you would identify their public IP blocks and restrict access accordingly:

| Protocol | Port | Remote CIDR | Description |
| :--- | :--- | :--- | :--- |
| TCP | 22 | `160.15.0.0/16` | LUC Campus Range (Example) |
| TCP | 443 | `160.15.0.0/16` | LUC HTTPS Access (Example) |

**OpenStack CLI Command:**
```bash
openstack security group rule create --protocol tcp --dst-port 22 --remote-ip 160.15.0.0/16 trusted-campus-access
```

> **Note**: The IP ranges used above are illustrative examples. To find your actual university IP ranges, check your university's IT documentation or use a tool like `curl ifconfig.me` while connected to the campus network to identify your current public IP.

## 4. Firewall Best Practices

### Avoid "The Global Open"
Never use `0.0.0.0/0` for SSH (Port 22), RDP (Port 3389), or Database ports (e.g., 5432, 3306). This exposes your VM to constant "brute-force" attacks from bots worldwide.

### Use a Bastion Host (Jump Box)
If you have many VMs in a private network, do not open SSH on all of them. Instead:
1. Create one small, highly hardened VM (the **Bastion Host**) with a public IP.
2. Open port 22 on the Bastion only for your university IP range.
3. Use the Bastion to "jump" into your other VMs using their private IPs.

### Regular Auditing
Periodically review your security group rules. Remove rules for projects that have ended or for users who no longer require access.

## Summary Decision Matrix

| Need | Recommended Rule | Risk Level |
| :--- | :--- | :--- |
| **Public Website** | TCP 80/443 $\rightarrow$ `0.0.0.0/0` | Low (Expected) |
| **Admin Access** | TCP 22 $\rightarrow$ `Campus IP Range` | Medium (Secure) |
| **Developer Access**| TCP 22 $\rightarrow$ `Home IP /32` | Medium (Secure) |
| **Internal API** | TCP 8080 $\rightarrow$ `Internal VPC Range` | Very Low (Isolated) |
| **Everything** | TCP 22 $\rightarrow$ `0.0.0.0/0` | **Critical (Dangerous)** |