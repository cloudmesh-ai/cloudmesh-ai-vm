# Data and Storage Management for Cloud VMs

This chapter explains how to manage data in a cloud environment, distinguishing between different types of storage and how to ensure your data survives VM failures or deletions.

## 1. Ephemeral vs. Persistent Storage

The most critical concept in cloud storage is the difference between where your OS lives and where your data lives.

- **Ephemeral Storage**: Storage that is physically attached to the host machine running the VM. It is extremely fast but **deleted** when the VM is terminated. Use this for swap space, temporary caches, and scratch files.
- **Persistent Storage**: Storage that exists independently of the VM (network-attached). If the VM is deleted, the storage volume remains. This is where your databases and user files must live.

## 2. Storage Types: Block, File, and Object

Cloud providers offer three primary ways to store data.

### Block Storage (e.g., AWS EBS, OpenStack Cinder)
Block storage behaves like a physical hard drive. You "attach" a volume to a VM, format it with a filesystem (like ext4 or xfs), and mount it to a directory.
- **Best for**: Databases, Boot disks, and any application that requires low-latency raw disk access.
- **Limitation**: Typically, a block volume can only be attached to one VM at a time.

### File Storage (e.g., NFS, Azure Files, AWS EFS)
File storage is a network-attached filesystem that can be mounted by **multiple VMs simultaneously**.
- **Best for**: Shared configuration files, web server assets (images/CSS) shared across a cluster, and home directories.
- **Limitation**: Slower than block storage due to network overhead.

### Object Storage (e.g., AWS S3, OpenStack Swift)
Object storage does not use a directory tree; it stores data as "objects" in "buckets" accessible via an API (HTTP).
- **Best for**: Backups, logs, images, and massive datasets for AI/ML.
- **Limitation**: You cannot "install" software on object storage; you must upload and download files via API or a mount tool like `s3fs`.

## 3. Practical Guide: Managing Block Storage on Linux

When you attach a new volume to a Linux VM, it doesn't appear as a folder automatically. You must prepare it.

### Step 1: Identify the Disk
Use `lsblk` to find the new device (e.g., `/dev/vdb`).
```bash
lsblk
```

### Step 2: Format the Disk
Create a filesystem on the raw block device.
```bash
sudo mkfs.ext4 /dev/vdb
```

### Step 3: Mount the Disk
Create a directory and mount the device to it.
```bash
sudo mkdir /mnt/data
sudo mount /dev/vdb /mnt/data
```

### Step 4: Make it Persistent (`/etc/fstab`)
To ensure the disk mounts automatically after a reboot, add it to `/etc/fstab`. First, get the UUID of the disk:
```bash
sudo blkid /dev/vdb
```
Then add a line like this to `/etc/fstab`:
`UUID=your-uuid-here /mnt/data ext4 defaults 0 2`

## 4. Data Protection and Recovery

### Snapshots
A snapshot is a point-in-time copy of a block volume. 
- **Use Case**: Take a snapshot before upgrading a database version. If the upgrade fails, you can restore the volume to exactly how it was.

### Backups
Snapshots are often stored on the same infrastructure as the VM. A true backup involves copying data to a separate region or an Object Storage bucket.

## 5. Comparison Matrix

| Feature | Block Storage | File Storage | Object Storage |
| :--- | :--- | :--- | :--- |
| **Access Method** | OS Filesystem | Network Mount | API (HTTP) |
| **Performance** | Very High | Moderate | Low (High Latency) |
| **Shared Access** | Single VM | Multiple VMs | Global / API |
| **Scaling** | Fixed Volume Size | Elastic | Virtually Infinite |
| **Example** | `/dev/vdb` | `/mnt/nfs/share` | `s3://my-bucket` |

## Summary Checklist
- [ ] Identify which data is ephemeral and which must be persistent.
- [ ] Use Block Storage for databases and File Storage for shared assets.
- [ ] Always use UUIDs in `/etc/fstab` rather than device names like `/dev/vdb`.
- [ ] Schedule regular snapshots of critical volumes.