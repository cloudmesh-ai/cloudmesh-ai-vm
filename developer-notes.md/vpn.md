# Understanding and Implementing Virtual Private Networks (VPNs)

This chapter explains the mechanics of Virtual Private Networks (VPNs), how to implement them using open-source software, and how to optimize traffic using split-tunneling techniques.

## 1. What is a VPN?

A Virtual Private Network (VPN) creates a secure, encrypted "tunnel" over a public network (like the internet). It allows a device to send and receive data as if it were directly connected to a private local network, regardless of its physical location.

### Core Concepts
- **Tunneling**: Encapsulating a private network packet inside a public network packet.
- **Encryption**: Ensuring that if a packet is intercepted in the "tunnel," it cannot be read without the correct key.
- **Virtual Interface**: When a VPN connects, the OS creates a new network interface (e.g., `tun0` or `wg0`) with its own private IP address.

## 2. Open Source VPN Software

For developers building their own command-line tools or infrastructure, two primary open-source projects dominate the landscape.

### WireGuard: The Modern Standard
WireGuard is a streamlined, high-performance VPN that uses state-of-the-art cryptography.
- **Pros**: Extremely fast, low power consumption, and a very small code base (easier to audit).
- **CLI Implementation**: It uses simple configuration files and a utility called `wg-quick`.

**Example CLI Setup**:
```bash
# Create a private key
wg genkey | tee privatekey | wg pubkey > publickey

# Use wg-quick to bring up the interface based on a config file
sudo wg-quick up wg0
```

### OpenVPN: The Flexible Legacy
OpenVPN is a highly configurable, mature VPN that can run over either UDP or TCP.
- **Pros**: Can be configured to run on port 443 (HTTPS), making it very difficult for firewalls to block.
- **CLI Implementation**: Uses `.ovpn` configuration files and the `openvpn` command.

**Example CLI Setup**:
```bash
# Start OpenVPN in the background using a config file
sudo openvpn --config client.ovpn --daemon
```

## 3. Split Tunneling (SplitVPN)

By default, most VPNs use a **Full Tunnel**, meaning *all* of your internet traffic is routed through the VPN server. This can cause slow speeds for general browsing and prevent you from accessing local devices (like your home printer).

**Split Tunneling** is the practice of routing only specific traffic through the VPN while letting the rest of your traffic use your local internet connection.

### How it Works: Routing Tables
Split tunneling is achieved by modifying the OS routing table. Instead of changing the "Default Gateway," you add specific routes for your target networks.

**Scenario**: You want to access a cloud network (`10.0.0.0/16`) via VPN, but you want to browse YouTube via your home ISP.

**Linux CLI Example (using `ip route`)**:
```bash
# 1. Connect to VPN (ensure it doesn't set a global default gateway)
# 2. Add a specific route for the cloud network via the VPN interface
sudo ip route add 10.0.0.0/16 dev wg0
```

### When to use Split Tunneling
- **Performance**: Avoid the latency of a VPN for non-sensitive traffic.
- **Local Access**: Maintain connectivity to local LAN resources while connected to a remote corporate network.
- **Bandwidth**: Prevent the VPN server from being bogged down by high-bandwidth traffic (like streaming) that doesn't need encryption.

## 4. Comparison: WireGuard vs. OpenVPN

| Feature | WireGuard | OpenVPN |
| :--- | :--- | :--- |
| **Performance** | Extremely High | Moderate |
| **Code Complexity** | Very Low (~4k lines) | High (~100k+ lines) |
| **Crypto** | Fixed, Modern (ChaCha20) | Negotiable (AES, etc.) |
| **Connection Speed** | Near Instant | Slower (Handshake required) |
| **Firewall Stealth** | Moderate (UDP only) | High (TCP 443 option) |

## Summary: Implementation Checklist

If you are building a command-line tool to manage VPNs, follow these guidelines:
- [ ] **Prefer WireGuard** for performance and simplicity.
- [ ] **Use OpenVPN** if you need to bypass strict corporate firewalls using TCP 443.
- [ ] **Implement Split Tunneling** by default to ensure users don't lose local network access.
- [ ] **Automate Routing**: Use scripts to dynamically add/remove routes based on the target environment.
- [ ] **Secure the Keys**: Store private keys in a secure location (e.g., using the techniques described in the `keyring.md` chapter).