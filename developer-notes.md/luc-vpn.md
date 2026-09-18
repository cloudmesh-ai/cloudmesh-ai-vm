# Connecting to the LUC VPN

This chapter provides a practical guide for students and faculty at Loyola University Chicago (LUC) to set up and optimize their VPN connections for accessing university resources and cloud environments.

## 1. Overview of LUC VPN Services

LUC provides VPN services to ensure that members of the university community can securely access internal systems (such as university file shares, administrative portals, and specialized research software) from any location.

### Common VPN Clients
LUC typically utilizes enterprise-grade VPN solutions. Depending on your account type and department, you may be using:
- **Cisco AnyConnect / Cisco Secure Client**: The primary tool for most university users.
- **GlobalProtect**: Used by specific administrative or technical divisions.
- **OpenVPN**: May be used for specific departmental research labs.

## 2. Setup and Authentication

### Accessing the VPN Portal
To establish your connection, visit the official LUC ITS help page:
**[LUC ITS VPN Support](https://www.luc.edu/its/)**

1. Navigate to the link above and search for "VPN" in the knowledge base.
2. Download the VPN client appropriate for your operating system.
3. Configure the client with the LUC VPN gateway address (provided by ITS).

### Authentication (MFA)
Like most modern institutions, LUC employs **Multi-Factor Authentication (MFA)** to prevent unauthorized access.
- After entering your LUC credentials, you will be prompted to verify your identity via a mobile app (such as Duo or Microsoft Authenticator).
- You must approve the request on your device to complete the tunnel establishment.

### Linux Setup Guide
For Linux users, you can establish the VPN connection using these methods:

1. **Official Cisco Secure Client**: Download the installer provided by LUC ITS and run it with root privileges:
   ```bash
   sudo sh anyconnect-linux-installer.sh
   ```
2. **OpenConnect (Open Source)**: For a command-line interface (CLI) experience, `openconnect` is a highly recommended open-source alternative.
   ```bash
   # Install openconnect
   sudo apt install openconnect  # Debian/Ubuntu
   sudo dnf install openconnect  # Fedora/RHEL

   # Connect to LUC VPN (replace vpn.luc.edu with the actual gateway provided by ITS)
   sudo openconnect vpn.luc.edu
   ```

## 3. Optimizing with Split Tunneling

Many university VPN configurations default to a "Full Tunnel" mode. While secure, this routes all your traffic—including streaming and personal browsing—through the LUC network, which can lead to increased latency and slower speeds.

### Implementing a Manual Split Tunnel
If you are using a CLI-based tool or have administrative control over your routing table, you can implement split-tunneling to route only LUC-destined traffic through the VPN.

**Scenario**: You need to access LUC internal resources (e.g., `160.15.0.0/16`) but want your general internet traffic to use your home ISP.

**Linux CLI Example**:
```bash
# Assuming your VPN interface is tun0
sudo ip route add 160.15.0.0/16 dev tun0
```

## 4. Troubleshooting Common Issues

- **Authentication Timeouts**: Ensure your MFA device is online. If the push notification doesn't arrive, check the "alternative verification methods" in the VPN prompt.
- **DNS Resolution**: If you cannot reach internal LUC sites by name, ensure your VPN is configured to use LUC's internal DNS servers. You may need to check your `/etc/resolv.conf` on Linux/macOS.
- **Local Network Conflicts**: If your home network uses the same IP range as the university (e.g., `192.168.1.x`), you may experience connectivity issues. Try changing your home router's local IP range.

## Summary Checklist
- [ ] Download the approved VPN client from LUC ITS.
- [ ] Complete the MFA registration on your mobile device.
- [ ] Test connectivity to a known internal LUC resource.
- [ ] (Optional) Configure split-tunneling to optimize internet performance.