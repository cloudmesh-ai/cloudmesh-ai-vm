import os
import subprocess
import logging
import json
import base64
import hashlib
from typing import List, Dict, Any, Optional
from pathlib import Path

from paramiko import PKey
from paramiko.ssh_exception import PasswordRequiredException

logger = logging.getLogger("cloudmesh.ai.vm")

class KeyManager:
    """
    Utility class for managing SSH keys and GitHub integration.
    """

    COMMON_KEY_NAMES = ["id_ed25519", "id_rsa", "id_ecdsa", "id_dsa"]

    def __init__(self):
        self.ssh_dir = Path.home() / ".ssh"

    def get_ssh_key_md5_fingerprint(self, key_string: str) -> str:
        """
        Derives the classic MD5 fingerprint of an SSH public key
        (equivalent to `ssh-keygen -E md5 -lf`).
        """
        try:
            parts = key_string.strip().split()
            if len(parts) < 2:
                return "N/A"

            # Extract the base64-encoded key data part
            key_data_b64 = parts[1]

            # Decode the base64 data into raw binary bytes
            key_bytes = base64.b64decode(key_data_b64)

            # Compute MD5 hash of the raw bytes
            md5_hash = hashlib.md5(key_bytes).hexdigest()

            # Format with colons to match standard ssh-keygen output (e.g., ab:cd:ef...)
            return ":".join(md5_hash[i:i+2] for i in range(0, len(md5_hash), 2))

        except Exception as e:
            logger.debug(f"Error computing MD5 fingerprint: {e}")
            return "N/A"

    def get_ssh_key_sha256_fingerprint(self, key_string: str) -> str:
        """
        Derives the modern SHA256 fingerprint of an SSH public key
        (equivalent to `ssh-keygen -lf`).
        """
        try:
            parts = key_string.strip().split()
            if len(parts) < 2:
                return "N/A"

            # Extract the base64-encoded key data part
            key_data_b64 = parts[1]

            # Decode the base64 data into raw binary bytes
            key_bytes = base64.b64decode(key_data_b64)

            # Compute SHA256 hash of the raw bytes
            sha256_digest = hashlib.sha256(key_bytes).digest()

            # Encode to base64 and strip trailing '=' padding per OpenSSH convention
            fingerprint_b64 = base64.b64encode(sha256_digest).decode('utf-8').rstrip('=')

            return f"SHA256:{fingerprint_b64}"

        except Exception as e:
            logger.debug(f"Error computing SHA256 fingerprint: {e}")
            return "N/A"

    def get_fingerprints(self, key_path: str) -> Dict[str, str]:
        """
        Retrieves the SSH fingerprints (both SHA256 and MD5) for a given key.
        """
        results = {"sha256": "unknown", "md5": "unknown"}
        try:
            # Get SHA256 (Default)
            res_sha = subprocess.run(
                ["ssh-keygen", "-lf", key_path],
                capture_output=True,
                text=True,
                check=True
            )
            parts_sha = res_sha.stdout.strip().split()
            for p in parts_sha:
                if p.startswith("SHA256:"):
                    results["sha256"] = p.split(":", 1)[1]
                    break
                if len(p) == 43 and p.count("/") == 0 and p[0].isalnum():
                     results["sha256"] = p
                     break

            # Get MD5 (Classic aa:bb:cc...)
            res_md5 = subprocess.run(
                ["ssh-keygen", "-E", "md5", "-lf", key_path],
                capture_output=True,
                text=True,
                check=True
            )
            parts_md5 = res_md5.stdout.strip().split()
            for p in parts_md5:
                if p.startswith("MD5:"):
                    results["md5"] = p.split(":", 1)[1]
                    break
                if p.count(":") == 5:
                    results["md5"] = p
                    break
        except Exception as e:
            logger.debug(f"Error getting fingerprints for {key_path}: {e}")

        return results

    def scan_local_keys(self) -> List[Dict[str, Any]]:
        """
        Scans the ~/.ssh directory for common private keys and checks for passphrases.
        """
        keys = []
        if not self.ssh_dir.exists():
            logger.warning(f"SSH directory not found: {self.ssh_dir}")
            return keys

        for file in self.ssh_dir.iterdir():
            is_common_name = any(file.name.startswith(name) for name in self.COMMON_KEY_NAMES)
            is_pem = file.suffix == ".pem"

            if (is_common_name or is_pem) and file.suffix != ".pub":
                key_type = self._get_key_type(file)
                has_passphrase = self._has_passphrase(file)
                fps = self.get_fingerprints(str(file))
                comment = self._get_key_comment(file)
                keys.append({
                    "path": str(file),
                    "type": key_type,
                    "sha256": fps["sha256"],
                    "md5": fps["md5"],
                    "comment": comment,
                    "has_passphrase": has_passphrase
                })

        return keys

    def _get_key_comment(self, key_path: Path) -> str:
        """
        Extracts the comment from the public key associated with the private key.
        """
        try:
            pub_file = key_path.with_suffix(key_path.suffix + ".pub")
            if pub_file.exists():
                pub_line = pub_file.read_text().strip().splitlines()[0]
                parts = pub_line.split()
                if len(parts) >= 3:
                    return " ".join(parts[2:])

            pub_out = subprocess.run(
                ["ssh-keygen", "-y", "-f", str(key_path)],
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL
            )
            if pub_out.returncode == 0:
                pub_line = pub_out.stdout.strip().splitlines()[0]
                parts = pub_line.split()
                if len(parts) >= 3:
                    return " ".join(parts[2:])
        except Exception as e:
            logger.debug(f"Error getting comment for {key_path}: {e}")

        return "N/A"

    def _get_key_type(self, key_path: Path) -> str:
        """
        Attempts to determine the key type from the file content or name.
        """
        try:
            with open(key_path, 'r') as f:
                first_line = f.readline().strip()
                if "OPENSSH PRIVATE KEY" in first_line:
                    if "ed25519" in key_path.name: return "ed25519"
                    if "rsa" in key_path.name: return "rsa"
                    if "ecdsa" in key_path.name: return "ecdsa"
                    if "dsa" in key_path.name: return "dsa"
                    return "openssh"
                if "RSA PRIVATE KEY" in first_line: return "rsa"
                if "DSA PRIVATE KEY" in first_line: return "dsa"
                if "EC PRIVATE KEY" in first_line: return "ecdsa"
                if "PRIVATE KEY" in first_line:
                    if "ed25519" in key_path.name: return "ed25519"
                    if "rsa" in key_path.name: return "rsa"
                    if "ecdsa" in key_path.name: return "ecdsa"
                    if "dsa" in key_path.name: return "dsa"
                    return "pkcs8"
        except Exception:
            pass

        name = key_path.name.lower()
        if "ed25519" in name: return "ed25519"
        if "rsa" in name: return "rsa"
        if "ecdsa" in name: return "ecdsa"
        if "dsa" in name: return "dsa"
        return "unknown"

    def _has_passphrase(self, key_path: Path) -> bool:
        """
        Checks whether a private key is protected by a passphrase
        without triggering an interactive prompt.
        """
        try:
            PKey.from_path(key_path)
            return False

        except PasswordRequiredException:
            return True

        except TypeError as e:
            message = str(e).lower()

            if (
                "password-protected" in message
                or "password was not provided" in message
            ):
                return True

            logger.debug(
                f"Error checking passphrase for {key_path}: {e}"
            )
            return False

        except Exception as e:
            logger.debug(
                f"Error checking passphrase for {key_path}: {e}"
            )
            return False

    def get_github_keys(self) -> List[Dict[str, Any]]:
        """
        Fetches the list of SSH keys from GitHub using the API.
        """
        try:
            result = subprocess.run(
                ["gh", "api", "user/keys"],
                capture_output=True,
                text=True,
                check=True
            )
            return json.loads(result.stdout)
        except Exception as e:
            logger.error(f"Failed to fetch GitHub keys via API: {e}")
            return []

    def verify_github_auth(self, key_path: str) -> Dict[str, Any]:
        """
        Verifies if a specific SSH key authenticates successfully with GitHub.
        """
        try:
            github_keys = self.get_github_keys()
            fps = self.get_fingerprints(key_path)
            local_sha256 = fps["sha256"]

            # 1. Match by fingerprint (Most reliable and fast)
            for gk in github_keys:
                if local_sha256 != "unknown" and gk.get("fingerprint") == local_sha256:
                    return {
                        "authenticated": True,
                        "title": gk.get("title"),
                        "fingerprint": gk.get("fingerprint") or local_sha256,
                        "created_at": gk.get("created_at", "N/A"),
                        "last_used": gk.get("last_used", "N/A")
                    }

            # 2. Match by public key content
            local_pub = None
            pub_file = Path(key_path).with_suffix(Path(key_path).suffix + ".pub")
            if pub_file.exists():
                try:
                    local_pub = pub_file.read_text().strip()
                except Exception as e:
                    logger.debug(f"Could not read pub file {pub_file}: {e}")

            if not local_pub:
                pub_out = subprocess.run(
                    ["ssh-keygen", "-y", "-f", key_path],
                    capture_output=True,
                    text=True,
                    stdin=subprocess.DEVNULL
                )
                local_pub = pub_out.stdout.strip()

            if local_pub:
                pub_parts = local_pub.split()
                # Extract only the base64 key material if present
                local_key_material = pub_parts[1] if len(pub_parts) >= 2 else local_pub

                for gk in github_keys:
                    if local_key_material and local_key_material in gk.get("key", ""):
                        return {
                            "authenticated": True,
                            "title": gk.get("title"),
                            "fingerprint": gk.get("fingerprint") or local_sha256,
                            "created_at": gk.get("created_at", "N/A"),
                            "last_used": gk.get("last_used", "N/A")
                        }

            # 3. Fallback to live connection check
            result = subprocess.run(
                ["ssh", "-i", key_path, "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", "git@github.com"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0 or "Hi" in result.stdout or "Hi" in result.stderr:
                return {
                    "authenticated": True,
                    "title": "Unknown (Live Auth)",
                    "fingerprint": local_sha256 if local_sha256 != "unknown" else fps["md5"],
                    "created_at": "N/A",
                    "last_used": "N/A"
                }

            return {"authenticated": False, "title": None, "fingerprint": None, "created_at": "N/A", "last_used": "N/A"}
        except Exception as e:
            logger.debug(f"Error verifying GitHub auth for {key_path}: {e}")
            return {"authenticated": False, "title": None, "fingerprint": None, "created_at": "N/A", "last_used": "N/A"}

    def github_upload(self, key_path: str) -> Dict[str, Any]:
        """
        Uploads a local SSH key to GitHub using the gh CLI.
        """
        private_key_path = Path(key_path)
        public_key_path = private_key_path.with_suffix(private_key_path.suffix + ".pub")
        if not public_key_path.exists():
            try:
                pub_out = subprocess.run(
                    ["ssh-keygen", "-y", "-f", str(private_key_path)],
                    capture_output=True,
                    text=True,
                    check=True
                )
                with open(public_key_path, "w") as f:
                    f.write(pub_out.stdout)
            except subprocess.CalledProcessError as e:
                return {"success": False, "error": f"Could not generate public key: {e.stderr}"}

        try:
            result = subprocess.run(
                ["gh", "ssh-key", "add", str(public_key_path)],
                capture_output=True,
                text=True,
                check=True
            )
            return {"success": True, "output": result.stdout}
        except subprocess.CalledProcessError as e:
            return {"success": False, "error": e.stderr or e.stdout}
        except FileNotFoundError:
            return {"success": False, "error": "GitHub CLI ('gh') not found. Please install it."}

    def find_key_path(self, public_key: str) -> Optional[str]:
        """
        Attempts to find a local private key that matches the given public key material.
        """
        if not public_key:
            return None

        # Normalize the public key material (remove type prefix if present)
        parts = public_key.split()
        material = parts[1] if len(parts) >= 2 else public_key

        # 1. First, try matching against existing .pub files (fastest and doesn't require passphrases)
        for file in self.ssh_dir.iterdir():
            if file.suffix == ".pub":
                try:
                    if material in file.read_text():
                        # Return the path to the private key (remove .pub extension)
                        return str(file.with_suffix(""))
                except Exception:
                    continue

        # 2. Fallback: try generating public keys from private keys
        for file in self.ssh_dir.iterdir():
            if file.suffix == ".pub":
                continue

            is_common_name = any(file.name.startswith(name) for name in self.COMMON_KEY_NAMES)
            is_pem = file.suffix == ".pem"
            if not (is_common_name or is_pem):
                continue

            try:
                pub_out = subprocess.run(
                    ["ssh-keygen", "-y", "-f", str(file)],
                    capture_output=True,
                    text=True,
                    stdin=subprocess.DEVNULL
                )
                if pub_out.returncode == 0:
                    generated_pub = pub_out.stdout.strip()
                    if material in generated_pub:
                        return str(file)
            except Exception:
                continue

        return None

    def github_list(self) -> List[Dict[str, Any]]:
        """
        Lists the SSH keys currently configured in GitHub and identifies their local paths.
        """
        keys = self.get_github_keys()
        for k in keys:
            local_path = self.find_key_path(k.get("key", ""))
            k["local_path"] = local_path if local_path else "Not found"

            # Calculate fingerprints from the public key material
            k["md5"] = self.get_ssh_key_md5_fingerprint(k.get("key", ""))
            k["sha256"] = self.get_ssh_key_sha256_fingerprint(k.get("key", ""))

        return keys
