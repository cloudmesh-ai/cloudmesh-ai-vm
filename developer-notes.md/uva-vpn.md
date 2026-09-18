# Connecting to the UVA VPN

This chapter provides a practical guide for students and researchers at the University of Virginia (UVA) to set up and optimize their VPN connections for accessing university resources and cloud environments.

## 1. Overview of UVA VPN Services

UVA provides VPN services to allow secure access to internal network resources (such as licensed software, internal databases, and departmental servers) from off-campus locations.

### Common VPN Clients
UVA typically utilizes industry-standard VPN clients. Depending on your department, you may be using:
- **Cisco AnyConnect / Cisco Secure Client**: The most common enterprise solution.
- **GlobalProtect**: Used by various university divisions.
- **OpenVPN**: Occasionally used for specific research clusters.

## 2. Setup and Authentication

### Accessing the VPN Portal
To get started, visit the official UVA ITS VPN portal:
**[UVA VPN Setup Guide](https://its.virginia.edu/vpn)**

1. Navigate to the link above.
2. Download the client compatible with your OS (Windows, macOS, Linux).
3. Enter the VPN server address (e.g., `vpn.virginia.edu` or a department-specific endpoint).

### Authentication (Duo MFA)
UVA requires **Multi-Factor Authentication (MFA)** for VPN access. 
- After entering your Computing ID and password, you will receive a Duo push notification.
- You must approve the push on your mobile device before the tunnel is established.

### Linux Setup Guide
For Linux users, you have two primary options:

1. **Official Cisco Secure Client**: Download the `.sh` or `.tgz` installer from the UVA VPN portal and run it with root privileges:
   ```bash
   sudo sh anyconnect-linux-installer.sh
   ```
2. **OpenConnect (Open Source)**: If you prefer a CLI tool, `openconnect` is an excellent open-source alternative to Cisco AnyConnect.
   ```bash
   # Install openconnect
   sudo apt install openconnect  # Debian/Ubuntu
   sudo dnf install openconnect  # Fedora/RHEL

   # Connect to UVA VPN
   sudo openconnect vpn.virginia.edu
   ```

## 3. Accessing Rivanna and Afton HPC
Once the VPN tunnel is established, you have network access to UVA's High-Performance Computing (HPC) resources.

### Connecting to Rivanna
Rivanna is the primary HPC cluster. To access it, use SSH from your terminal:
```bash
ssh username@rivanna.hpc.virginia.edu
```

### Connecting to Afton
Afton is often used for specific workloads or as a secondary cluster. Access it similarly:
```bash
ssh username@afton.hpc.virginia.edu
```

**Important**: You must be connected to the VPN (or be on the physical campus network) for these addresses to resolve and accept connections. If you experience "Connection Timeout," verify that your VPN is active and that you have passed the Duo MFA prompt.

## 4. Optimizing with Split Tunneling

By default, many university VPNs are configured as "Full Tunnels," routing all your internet traffic through the university. This can slow down your connection and may restrict access to some local services.

### Implementing a Manual Split Tunnel
If your client allows it, or if you are using a CLI-based tool, you can manually route only UVA-specific traffic through the VPN.

**Scenario**: You want to access UVA internal resources (e.g., `128.142.0.0/16`) via VPN, but keep your general web traffic on your home ISP.

**Linux CLI Example**:
```bash
# Assuming your VPN interface is tun0
sudo ip route add 128.142.0.0/16 dev tun0
```

## 4. Troubleshooting Common Issues

- **Duo Push Not Arriving**: Ensure your mobile device has a stable data connection. Try the "Call Me" option in the Duo prompt.
- **DNS Resolution Failures**: If you can ping an internal IP but cannot resolve a `.virginia.edu` hostname, check if your DNS settings were updated by the VPN. You may need to manually add UVA DNS servers to your `/etc/resolv.conf`.
- **Slow Connection**: Check if you are using a "Full Tunnel." If so, try to configure a split tunnel as described in Section 3.

## Summary Checklist
- [ ] Download the correct client from UVA ITS.
- [ ] Configure Duo MFA on your mobile device.
- [ ] Verify connectivity to an internal UVA resource.
- [ ] (Optional) Configure split-tunneling to improve general internet speed.