# Using the System Keyring for Secure Secret Storage

This chapter describes how to use the system keyring to store and retrieve sensitive credentials. By leveraging the operating system's native secure storage, you can avoid storing passwords in plain-text files or exposing them through environment variables.

## 1. What is a System Keyring?

A system keyring is a secure, encrypted database managed by the operating system to store passwords, keys, and other small pieces of sensitive data. Instead of creating your own encryption logic, your application delegates the storage and encryption to the OS.

### Supported Backends
The `keyring` Python library automatically detects and uses the best available backend for your platform:
- **macOS**: Keychain Access
- **Windows**: Windows Credential Manager
- **Linux**: Secret Service (GNOME Keyring) or KWallet (KDE)

## 2. Why Use a Keyring?

Compared to other common storage methods, the system keyring offers several security advantages:

| Method | Storage Format | Security Level | Main Risk |
| :--- | :--- | :--- | :--- |
| **.env / YAML** | Plain-text file | Low | Accidental Git commits |
| **Env Vars** | Memory/Process | Medium | Leaked via `ps` or logs |
| **System Keyring** | OS-Encrypted | High | Requires unlocked OS session |
| **Cloud Vault** | Remote API | Highest | Network dependency / API key |

## 3. Implementation Guide

### Installation

Install the `keyring` library via pip:

```bash
pip install keyring
```

### Basic Operations

The `keyring` library uses a simple key-value pair system based on a **Service Name** and a **Username**.

```python
import keyring

# Define your service and account identifiers
SERVICE_NAME = "cloudmesh"
ACCOUNT_NAME = "aws.secret_access_key"
SECRET_VALUE = "AKIA-EXAMPLE-12345"

# 1. Store a secret
keyring.set_password(SERVICE_NAME, ACCOUNT_NAME, SECRET_VALUE)
print(f"Secret stored successfully for {ACCOUNT_NAME}.")

# 2. Retrieve a secret
retrieved_secret = keyring.get_password(SERVICE_NAME, ACCOUNT_NAME)
if retrieved_secret:
    print(f"Retrieved secret: {retrieved_secret}")
else:
    print("Secret not found.")

# 3. Delete a secret
keyring.delete_password(SERVICE_NAME, ACCOUNT_NAME)
print("Secret deleted.")
```

## 4. Advanced Integration Patterns

### Tiered Secret Resolution

A professional application should not rely on a single source of truth. Instead, implement a "fallback" mechanism that checks the keyring first, then a config file, then environment variables.

```python
import os
import keyring

def get_secret(cloud_name, key_name, env_var=None):
    """
    Resolves a secret using a tiered priority:
    1. System Keyring
    2. Environment Variable
    3. Default fallback
    """
    # Priority 1: System Keyring (Securest)
    service = "cloudmesh"
    account = f"{cloud_name}.{key_name}"
    val = keyring.get_password(service, account)
    if val:
        return val

    # Priority 2: Environment Variable
    if env_var and env_var in os.environ:
        return os.environ[env_var]

    return None

# Usage
aws_key = get_secret("aws", "access_key", env_var="AWS_ACCESS_KEY_ID")
```

### Organizing Multi-Cloud Secrets

To avoid collisions between different cloud providers, use a structured naming convention for your account identifiers:

- `cloudmesh` (Service) $\rightarrow$ `azure.client_id` (Account)
- `cloudmesh` (Service) $\rightarrow$ `azure.client_secret` (Account)
- `cloudmesh` (Service) $\rightarrow$ `gcp.project_id` (Account)

## 5. Important Considerations

### The "Headless" Server Problem
System keyrings usually require an active, unlocked user session to access the encrypted store. This creates a challenge for **headless servers** or **CI/CD pipelines** (like GitHub Actions) where no GUI session exists.

**Solutions for Headless Environments**:
- **Environment Variables**: Use secrets injected by the CI/CD provider.
- **Local Vaults**: Run a lightweight HashiCorp Vault instance in dev mode.
- **Keyring Backends**: Use the `keyring.backends.failwhale.Keyring` for testing or specific file-based encrypted backends.

### Security Limits
While the keyring is secure, it is only as safe as the OS user account. If an attacker gains full access to your logged-in user session, they may be able to programmatically retrieve secrets from the keyring. Always combine keyring usage with the **Principle of Least Privilege**.