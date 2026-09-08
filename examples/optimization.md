# Performance Tuning and Optimization for Cloud VMs

This chapter explains how to move beyond "out-of-the-box" settings to maximize the performance of your cloud virtual machines. Optimization is particularly critical for High-Performance Computing (HPC), AI/ML workloads, and high-traffic web servers.

## 1. The Optimization Mindset

Performance tuning is an iterative process of **Measure $\rightarrow$ Tune $\rightarrow$ Verify**. Never apply optimizations without first establishing a baseline using the tools described in `monitoring.md`.

## 2. Kernel Tuning with `sysctl`

The Linux kernel comes with safe defaults, but these are often too conservative for high-performance cloud workloads. You can tune these at runtime using the `sysctl` command or permanently in `/etc/sysctl.conf`.

### Networking Optimizations
For servers handling thousands of concurrent connections, the default TCP stack can become a bottleneck.

- **TCP Window Scaling**: Allows for larger windows of data to be sent before requiring an acknowledgment.
- **Max Connections**: Increase the limit of pending connections in the queue.

**Example `/etc/sysctl.conf` additions**:
```bash
# Increase the maximum number of open files
fs.file-max = 2097152

# Optimize TCP for high-latency, high-bandwidth links
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
net.ipv4.tcp_rmem = 4096 87380 16777216
net.ipv4.tcp_wmem = 4096 65536 16777216
net.ipv4.tcp_slow_start_after_idle = 0
```

### Virtual Memory Tuning
- **Swappiness**: Controls how aggressively the kernel moves memory to the swap disk. For databases or HPC, you usually want this low to avoid disk latency.
  - `vm.swappiness = 10` (Tell the kernel to avoid swapping unless absolutely necessary).

## 3. CPU Optimization for HPC and AI

In a cloud environment, your VM shares a physical CPU with other tenants. To get consistent performance, you need to manage how your processes interact with the hardware.

### CPU Pinning (Affinity)
Context switching (when the CPU jumps between different tasks) creates overhead. CPU pinning binds a process to a specific physical core.
- **Tool**: `taskset`
- **Example**: `taskset -c 0,1 my_heavy_app` (Runs the app only on cores 0 and 1).

### NUMA (Non-Uniform Memory Access)
On large VMs with many cores, not all memory is equally "close" to every CPU. Accessing "remote" memory is slower.
- **Tool**: `numactl`
- **Example**: `numactl --cpunodebind=0 --membind=0 my_app` (Ensures the app uses memory and CPU from the same local node).

## 4. Disk I/O Optimization

Disk latency is the most common bottleneck in cloud computing.

### Filesystem Choice
- **EXT4**: Great for general purpose.
- **XFS**: Superior for very large files and high-concurrency I/O.

### Mount Options
The `noatime` mount option prevents the OS from writing to the disk every time a file is simply *read*. This significantly reduces write IOPS.
- **Action**: Edit `/etc/fstab` and change `defaults` to `defaults,noatime`.

### I/O Schedulers
Depending on your storage type (SSD vs. HDD), you should change the I/O scheduler:
- **Deadline/None**: Best for SSDs and NVMe (reduces CPU overhead).
- **CFQ**: Better for spinning disks.

## 5. Optimization "Quick Wins" Matrix

| Target | Action | Expected Result | Complexity |
| :--- | :--- | :--- | :--- |
| **Web Server** | Tune TCP `rmem`/`wmem` | Lower latency, more connections | Medium |
| **Database** | `vm.swappiness = 10` | Reduced disk thrashing | Low |
| **HPC App** | Use `numactl` | Lower memory access latency | Medium |
| **File Server** | Mount with `noatime` | Reduced metadata write overhead | Low |
| **AI Model** | PCIe Pass-through (GPU) | Massive throughput increase | High |

## Summary Checklist
- [ ] Establish a performance baseline using `htop` and `iotop`.
- [ ] Apply networking tuning via `sysctl` if handling high traffic.
- [ ] Set `vm.swappiness` to 10 for memory-intensive apps.
- [ ] Use `noatime` in `/etc/fstab` for all data volumes.
- [ ] Use `numactl` if your VM has more than 16-32 vCPUs.