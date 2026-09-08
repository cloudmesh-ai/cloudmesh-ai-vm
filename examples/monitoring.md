# Monitoring and Observability for Cloud VMs

This chapter explains how to monitor the health, performance, and stability of your cloud virtual machines. Monitoring is the difference between knowing a server is "down" and knowing *why* it is down.

## 1. The Three Pillars of Observability

To fully understand a VM's state, you need three types of data:
- **Metrics**: Numerical data over time (e.g., CPU usage is at 85%).
- **Logs**: Text records of events (e.g., "SSH login failed for user root").
- **Traces**: The path of a request as it moves through your system (critical for the Service Mesh discussed in `service-mesh.md`).

## 2. Local Resource Monitoring (The CLI Toolkit)

When you SSH into a VM, these are the primary tools for immediate diagnostics.

### CPU and Memory
- **`htop`**: An interactive process viewer. It shows CPU usage per core, memory consumption, and allows you to kill runaway processes.
- **`top`**: The standard, non-interactive version of htop. Available on almost every Unix-like system.
- **`free -m`**: Displays the amount of free and used memory in megabytes. Pay close attention to "available" memory rather than "free."

### Disk and I/O
- **`df -h`**: "Disk Free" in human-readable format. Use this to see if a partition (like `/var/log`) is 100% full, which often crashes applications.
- **`iotop`**: Shows which processes are currently reading from or writing to the disk. High "IO Wait" in htop usually indicates a disk bottleneck.

### Network Connectivity
- **`ss -tunlp`**: (Socket Statistics) The modern replacement for `netstat`. It shows which ports are listening and which processes are using them.
- **`tcpdump`**: A powerful packet sniffer. Use this to verify if traffic is actually reaching your VM (e.g., `sudo tcpdump port 22` to see SSH attempts).
- **`curl -v`**: Use the verbose flag to debug HTTP connectivity and see header exchanges.

## 3. System Logs and Debugging

Logs are the "black box" of your server. Most modern Linux distributions use `systemd`.

### Using `journalctl`
`journalctl` is the primary tool for querying the systemd journal.
- **View all logs**: `sudo journalctl`
- **Follow logs in real-time**: `sudo journalctl -f`
- **Filter by service**: `sudo journalctl -u nginx` (View only Nginx logs).
- **Filter by time**: `sudo journalctl --since "1 hour ago"`

### Traditional Log Files
Some applications still write to `/var/log/`.
- `/var/log/auth.log` or `/var/log/secure`: SSH and authentication attempts.
- `/var/log/syslog` or `/var/log/messages`: General system events.

## 4. Cloud-Level Monitoring

While local tools are great for debugging, you cannot SSH into 100 VMs to check `htop`. Cloud providers offer centralized monitoring.

- **Agent-Based Monitoring**: You install a small program (like the CloudWatch agent or Prometheus Node Exporter) that pushes metrics to a central dashboard.
- **Hypervisor Monitoring**: The cloud provider monitors the VM from the "outside" (e.g., CPU usage reported by the host), which requires no installation but provides less detail.

## 5. Common "Red Flags" to Watch For

| Symptom | Likely Cause | Tool to Verify |
| :--- | :--- | :--- |
| **High Load Average** | CPU saturation or Disk I/O wait | `htop` $\rightarrow$ check `%wa` (I/O wait) |
| **Out of Memory (OOM)** | Application memory leak | `dmesg \| grep -i oom` |
| **Connection Refused** | Process crashed or Firewall blocking | `ss -tunlp` $\rightarrow$ check if port is listening |
| **Disk Full** | Log file explosion | `df -h` $\rightarrow$ check `/var/log` |

## Summary Checklist
- [ ] Install `htop` and `iotop` for better visibility.
- [ ] Verify that your application logs are being captured by `journalctl`.
- [ ] Set up a basic cloud alert for CPU $> 90\%$ or Disk $> 80\%$.
- [ ] Test a `tcpdump` capture to understand your network traffic flow.