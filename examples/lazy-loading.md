# Implementing Lazy-Loading for Multi-Cloud SDKs

This chapter describes how to design a Python package that dynamically loads cloud SDKs (such as `boto3`, `azure-mgmt`, and `google-cloud`) only when they are actually required. This plugin-based architecture prevents "dependency bloat," ensuring that users only install the libraries necessary for the clouds they are targeting.

## 1. Dependency Management via Optional Extras

To allow users to install only the required SDKs, use **optional dependencies** (extras) in your `pyproject.toml`.

```toml
[project]
name = "mycloudpkg"
version = "0.1.0"
dependencies = ["pyyaml>=6.0", "cryptography>=41.0.0", "keyring>=24.0.0", "click>=8.1.0"]

[project.optional-dependencies]
libcloud = ["apache-libcloud>=3.8.0"]
boto = ["boto3>=1.28.0"]
azure = ["azure-identity>=1.14.0", "azure-mgmt-resource>=23.0.0"]
google = ["google-cloud-compute>=1.14.0"]
all = [
    "apache-libcloud>=3.8.0",
    "boto3>=1.28.0",
    "azure-identity>=1.14.0",
    "azure-mgmt-resource>=23.0.0",
    "google-cloud-compute>=1.14.0",
]
```

**Installation Examples:**
- Only AWS: `pip install mycloudpkg[boto]`
- AWS and Azure: `pip install mycloudpkg[boto,azure]`
- All providers: `pip install mycloudpkg[all]`

## 2. Plugin Architecture Implementation

### Base Provider and Dependency Checker

The core of the lazy-loading mechanism is a helper function that attempts to import a module and provides a clear error message with installation instructions if the module is missing.

```python
import importlib
from abc import ABC, abstractmethod
from typing import Any

class BaseProvider(ABC):
    """Abstract Base Class for all Cloud Providers."""
    @abstractmethod
    def connect(self) -> Any:
        pass

def check_dependency(module_name: str, extra_name: str):
    """Ensures required dependency is installed, or gives clear install instructions."""
    try:
        return importlib.import_module(module_name)
    except ImportError:
        raise ImportError(
            f"Required package '{module_name}' is not installed. "
            f"Install it using: pip install mycloudpkg[{extra_name}]"
        )
```

### Example Provider: AWS (Boto3)

Providers perform the lazy-import inside their `__init__` or `connect` methods.

```python
from mycloudpkg.providers.base import BaseProvider, check_dependency

class AWSProvider(BaseProvider):
    def __init__(self, config, **kwargs):
        # Dynamically verify and load boto3
        self.boto3 = check_dependency("boto3", "boto")
        self.region = kwargs.get("region") or config.get("aws", "region", default="us-east-1")
        self.client = None

    def connect(self):
        # Session initialization using lazy-loaded boto3
        import boto3
        session = boto3.Session(region_name=self.region)
        self.client = session.client("ec2")
        return self.client
```

### The Cloud Manager

The `CloudManager` acts as the orchestrator, mapping provider keys to their respective classes and instantiating them on demand.

```python
import importlib
from typing import Dict, List, Type
from mycloudpkg.providers.base import BaseProvider

class CloudManager:
    _PROVIDER_MAP = {
        "aws": ("mycloudpkg.providers.aws", "AWSProvider"),
        "azure": ("mycloudpkg.providers.azure", "AzureProvider"),
        "google": ("mycloudpkg.providers.google", "GCPProvider"),
        "libcloud": ("mycloudpkg.providers.libcloud", "LibcloudProvider"),
    }

    def __init__(self, providers: List[str], config, **config_overrides):
        self.config = config
        self.active_providers: Dict[str, BaseProvider] = {}
        self._load_providers(providers, **config_overrides)

    def _load_providers(self, providers: List[str], **config_overrides):
        for key in providers:
            key_lower = key.lower()
            if key_lower not in self._PROVIDER_MAP:
                raise ValueError(f"Unsupported cloud provider: '{key}'")

            mod_path, class_name = self._PROVIDER_MAP[key_lower]
            module = importlib.import_module(mod_path)
            provider_class: Type[BaseProvider] = getattr(module, class_name)

            provider_kwargs = config_overrides.get(key_lower, {})
            self.active_providers[key_lower] = provider_class(config=self.config, **provider_kwargs)

    def get_provider(self, name: str) -> BaseProvider:
        return self.active_providers[name.lower()]
```

## 3. Secure Configuration Management

To avoid hardcoding secrets, the package uses a tiered configuration system that reads from a YAML file, environment variables, and the system keyring.

### The Configuration Loader

The `Config` class implements a resolution hierarchy:
1. **System Keyring**: Native OS store (macOS Keychain, etc.).
2. **Encrypted YAML**: Values in `cloudmesh.yaml` prefixed with `enc:`.
3. **Environment Variables**: OS-level variables.
4. **Default Value**: Fallback.

```python
import os
import yaml
from pathlib import Path
from typing import Any, Dict, Optional
from mycloudpkg.security import SecretVault

class Config:
    def __init__(self, config_path: Optional[str] = None, passphrase: Optional[str] = None):
        self.data: Dict[str, Any] = {}
        self.passphrase = passphrase or os.environ.get("CLOUDMESH_KEY")
        self.config_path = Path(config_path).expanduser().resolve() if config_path \
                           else Path("~/.cloudmesh/cloudmesh.yaml").expanduser().resolve()
        self._load_yaml()

    def _load_yaml(self) -> None:
        if self.config_path.exists():
            with open(self.config_path, "r", encoding="utf-8") as f:
                self.data = yaml.safe_load(f) or {}

    def get(self, cloud_name: str, key: str, env_var: Optional[str] = None, default: Any = None) -> Any:
        # 1. Try Keyring
        val = SecretVault.get_from_keyring(cloud_name, key)
        if val: return val

        # 2. Try YAML (with decryption)
        cloud_cfg = self.data.get("cloudmesh", {}).get("cloud", {}).get(cloud_name, {}).get("credentials", {})
        if key in cloud_cfg and cloud_cfg[key] is not None:
            raw_val = str(cloud_cfg[key])
            if raw_val.startswith("enc:"):
                return SecretVault.decrypt_value(raw_val, passphrase=self.passphrase)
            return cloud_cfg[key]

        # 3. Try Environment Variable
        if env_var and env_var in os.environ:
            return os.environ[env_var]

        return default
```

### Secret Security with Fernet and Keyring

The `SecretVault` class handles symmetric encryption using the `cryptography` library and interacts with the `keyring` package.

```python
import os
import keyring
import base64
import hashlib
from cryptography.fernet import Fernet

class SecretVault:
    SERVICE_NAME = "cloudmesh"

    @staticmethod
    def _get_fernet_key(passphrase: str) -> bytes:
        key = hashlib.sha256(passphrase.encode()).digest()
        return base64.urlsafe_b64encode(key)

    @classmethod
    def encrypt_value(cls, raw_str: str, passphrase: str) -> str:
        fernet = Fernet(cls._get_fernet_key(passphrase))
        return f"enc:{fernet.encrypt(raw_str.encode('utf-8')).decode('utf-8')}"

    @classmethod
    def decrypt_value(cls, encrypted_str: str, passphrase: Optional[str] = None) -> str:
        if not encrypted_str.startswith("enc:"): return encrypted_str
        key_source = passphrase or os.environ.get("CLOUDMESH_KEY")
        fernet = Fernet(cls._get_fernet_key(key_source))
        return fernet.decrypt(encrypted_str[4:].encode("utf-8")).decode("utf-8")

    @classmethod
    def set_in_keyring(cls, cloud_name: str, key: str, value: str) -> None:
        keyring.set_password(cls.SERVICE_NAME, f"{cloud_name}.{key}", value)

    @classmethod
    def get_from_keyring(cls, cloud_name: str, key: str) -> Optional[str]:
        return keyring.get_password(cls.SERVICE_NAME, f"{cloud_name}.{key}")
```

## 4. Secret Management CLI (`cms`)

To simplify the management of encrypted secrets and keyring entries, a CLI tool is provided using `click`.

### Key Commands

- **Encrypt a secret for YAML**: 
  `cms sec encrypt "my-secret-key" --key "my-passphrase"`
- **Store a secret in the OS Keyring**: 
  `cms sec keyring-set --cloud aws --key AWS_SECRET_ACCESS_KEY`
- **Automatically encrypt all secrets in `cloudmesh.yaml`**: 
  `cms sec encrypt-yaml`

### Implementation Overview

The CLI uses `click` groups to organize security commands (`cms sec ...`). The `encrypt-yaml` command specifically scans the configuration file for keywords like "secret", "key", or "password" and encrypts any unencrypted values it finds.