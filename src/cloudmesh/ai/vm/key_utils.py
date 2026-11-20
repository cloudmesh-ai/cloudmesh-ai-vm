
import os
from pathlib import Path

from cloudmesh.ai.vm.diagnostics.config_validator import VMCommandError


def resolve_key_path(cloud_config: dict) -> tuple[Path, str]:
    """Resolve the SSH key path and derive the key name.

    Explicit key_path configuration takes precedence.

    Otherwise, discover SSH keys in ~/.ssh:
    - One logical key: use it.
    - No keys: raise VMCommandError.
    - Multiple keys: require explicit configuration.

    When both private and public files exist, prefer the private key.

    Returns:
        tuple[Path, str]: Absolute key path and key name without
        a trailing .pub suffix.
    """

    # 1. Use explicitly configured key path.
    key_path_raw = cloud_config.get("key_path")

    if key_path_raw:
        if not isinstance(key_path_raw, (str, os.PathLike)):
            raise VMCommandError("Invalid SSH key path configuration.")

        key_path = Path(os.path.expanduser(key_path_raw)).resolve()

        if not key_path.is_file():
            raise VMCommandError(
                f"SSH key file does not exist: {key_path}"
            )

    else:
        # 2. Automatically discover SSH keys.
        ssh_dir = Path.home() / ".ssh"

        if not ssh_dir.is_dir():
            raise VMCommandError(
                "No ~/.ssh directory found. Please create an SSH key "
                "or set 'key_path' in clouds.yaml."
            )

        excluded_files = {
            "config",
            "known_hosts",
            "authorized_keys",
            "environment",
        }

        files = [
            p for p in ssh_dir.iterdir()
            if p.is_file()
            and p.name not in excluded_files
            and (p.suffix == "" or p.suffix == ".pub")
        ]

        # Group public and private files by their logical key name.
        keys = {}

        for file in files:
            key_name = file.name.removesuffix(".pub")

            if key_name not in keys:
                keys[key_name] = {}

            if file.suffix == ".pub":
                keys[key_name]["public"] = file
            else:
                keys[key_name]["private"] = file

        if len(keys) == 0:
            raise VMCommandError(
                "No SSH key files found in ~/.ssh. Create an SSH key "
                "or set 'key_path' in clouds.yaml."
            )

        if len(keys) > 1:
            raise VMCommandError(
                "Multiple SSH keys detected in ~/.ssh. Set the desired "
                "one via 'key_path' in clouds.yaml."
            )

        # Prefer the private key when available.
        key_files = next(iter(keys.values()))

        key_path = (
            key_files.get("private")
            or key_files.get("public")
        ).resolve()

    # 3. Derive the cloud key-pair name.
    key_name = key_path.name.removesuffix(".pub")

    return key_path, key_name
