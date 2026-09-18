# Identity and Access Management (IAM) for Cloud VMs

This chapter explains how to manage permissions in the cloud. While SSH keys (discussed in `ssh-keys.md`) manage *how* you get into a VM, IAM manages *what* that VM is allowed to do once it is running.

## 1. Beyond the SSH Key: Identity-Based Access

In a traditional server, if an application needs to upload a file to a storage bucket, you would store an API key or a password in a config file on the disk. This is a major security risk: if the VM is compromised, the attacker has the key.

**Cloud IAM (Identity and Access Management)** replaces static keys with **Identities**. Instead of a password, the VM is assigned a "Service Account" or "Instance Profile." The cloud provider then automatically provides temporary, rotating tokens to the VM's metadata service.

## 2. Core IAM Concepts

### Service Accounts / Instance Profiles
A Service Account is a non-human identity. When you launch a VM, you can attach a specific identity to it.
- **Example**: A "Backup-VM" is assigned a role that allows it to write to a specific backup bucket but forbids it from deleting any files.
- **Benefit**: No passwords are ever stored on the disk. The application simply asks the cloud metadata service for a token.

### Role-Based Access Control (RBAC)
RBAC simplifies permission management by grouping permissions into "Roles."
- **Permission**: A single action (e.g., `s3:GetObject`).
- **Role**: A collection of permissions (e.g., "Storage Reader" = `s3:GetObject` + `s3:ListBucket`).
- **Assignment**: You assign the "Storage Reader" role to the VM's identity.

## 3. The Principle of Least Privilege (PoLP)

The goal of IAM is to ensure that every identity has the absolute minimum permissions necessary to perform its job.

### Bad Practice: The "Admin" Role
Assigning a "Project Admin" role to a VM. If the VM is hacked, the attacker can delete your entire cloud project.

### Good Practice: Granular Roles
Break down your identities by function:
- **Web-Server Identity**: Can read from the database, but cannot modify the database schema.
- **Log-Shipper Identity**: Can write to the log bucket, but cannot read any existing logs.
- **Monitoring Identity**: Can read CPU metrics, but cannot change any VM settings.

## 4. Temporary Credentials and Token Rotation

One of the most powerful features of cloud IAM is **Automatic Rotation**.

When a VM uses an Instance Profile, it doesn't get a permanent key. It gets a token that expires every few hours. The cloud provider's agent on the VM automatically refreshes this token in the background.
- **Security Win**: Even if an attacker manages to steal a token from memory, the token will expire shortly, limiting the window of opportunity for the attack.

## 5. Comparison: Static Keys vs. Cloud IAM

| Feature | Static API Keys / Passwords | Cloud IAM Identities |
| :--- | :--- | :--- |
| **Storage** | Stored in `.env` or config files | No keys stored on disk |
| **Rotation** | Manual (Rarely done) | Automatic (Every few hours) |
| **Scope** | Often too broad | Granular (Role-based) |
| **Leak Risk** | Permanent compromise | Short-lived compromise |
| **Management** | Decentralized | Centralized via Cloud Console |

## Summary Checklist
- [ ] Audit your VMs: Remove all static API keys from config files.
- [ ] Create specific Service Accounts for different application functions.
- [ ] Assign the most restrictive Role possible (Least Privilege).
- [ ] Use Instance Profiles to leverage automatic token rotation.