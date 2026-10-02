import subprocess
import re
import shutil
from typing import List, Dict, Any, Optional
from ..LocalBaseManager import LocalBaseManager
from cloudmesh.ai.vm.exceptions import VMProviderError, ConfigError, VMResourceError, VMAuthError, VMNetworkError

class Provider(LocalBaseManager):
    """
    WSL2 implementation of the CloudBaseManager.
    Uses the 'wsl.exe' CLI tool to manage Linux distributions.
    """

    def __init__(self, config: Any, console=None, **kwargs):
        super().__init__(config, console=console, **kwargs)
        self.cloud_name = "wsl2"

    def _wsl_command(self) -> str:
        """Return the WSL CLI executable available in this environment."""
        if shutil.which("wsl.exe"):
            return "wsl.exe"
        if shutil.which("wsl"):
            return "wsl"
        return "wsl.exe"

    @staticmethod
    def _normalize_wsl_output(output: str) -> str:
        """Normalize Windows-side WSL CLI output when called from WSL."""
        if "\x00" in output:
            return output.encode("utf-8").decode("utf-16le")
        return output

    def start(self, name: Optional[str] = None, flavor: Optional[str] = None, image: Optional[str] = None) -> str:
        """
        Starts a WSL2 distribution.
        If the distribution doesn't exist, it attempts to import it from a rootfs image.
        """
        if not name:
            raise ConfigError("WSL2 requires a specific distribution name to start.")

        # Check if distro already exists
        if self.exists(name):
            try:
                self._run_command([self._wsl_command(), "-d", name])
                return name
            except Exception as e:
                raise VMProviderError(f"Failed to start existing WSL2 distribution {name}: {e}")

        # Attempt to import if not exists
        cloud_config = self.get_cloud_config("wsl2")
        # Use image override if provided, otherwise fallback to config 'rootfs'
        rootfs = image or cloud_config.get("rootfs")
        install_dir = cloud_config.get("install_dir", "C:\\WSL")

        if not rootfs:
            raise ConfigError(f"Rootfs image path not configured in YAML for wsl2. Cannot import {name}.")

        try:
            # wsl --import <Distro> <InstallLocation> <FileName>
            self._run_command([self._wsl_command(), "--import", name, install_dir, rootfs])
            self._run_command([self._wsl_command(), "-d", name])
            return name
        except Exception as e:
            raise VMProviderError(f"Failed to import and start WSL2 distribution {name}: {e}")

    def stop(self, name: Optional[str] = None) -> bool:
        """
        Stops (terminates) a WSL2 distribution.
        """
        if not name or not self.exists(name):
            raise VMResourceError(f"Distribution {name} not found.")

        try:
            self._run_command([self._wsl_command(), "--terminate", name])
            return True
        except Exception as e:
            raise VMProviderError(f"Failed to stop WSL2 distribution {name}: {e}")

    def delete(self, name: Optional[str] = None) -> bool:
        """
        Deletes (unregisters) a WSL2 distribution.
        """
        if not name or not self.exists(name):
            raise VMResourceError(f"Distribution {name} not found.")

        try:
            self._run_command([self._wsl_command(), "--unregister", name])
            return True
        except Exception as e:
            raise VMProviderError(f"Failed to delete WSL2 distribution {name}: {e}")

    def list(self) -> List[Dict[str, Any]]:
        """
        Lists WSL2 distributions.
        """
        try:
            result = self._run_command([self._wsl_command(), "--list", "--verbose"])
            lines = self._normalize_wsl_output(result.stdout).strip().splitlines()
            if len(lines) < 2:
                return []

            vms = []
            for line in lines[1:]:
                parts = line.split()
                if parts and parts[0] == "*":
                    parts = parts[1:]
                if len(parts) >= 2:
                    vms.append({
                        "Name": parts[0],
                        "State": parts[1],
                        "Version": parts[2] if len(parts) > 2 else "Unknown"
                    })
            return vms
        except Exception:
            return []

    def login(self, name: Optional[str] = None) -> bool:
        """
        Logs into a WSL2 distribution.
        """
        if not name:
            self.print("Error: Distro name is required to login.")
            return False

        try:
            # launch interactive shell
            subprocess.run([self._wsl_command(), "-d", name], check=True)
            return True
        except Exception:
            return False

    def suspend(self, name: Optional[str] = None) -> bool:
        """
        WSL2 doesn't have a 'suspend' mode; we use terminate.
        """
        return self.stop(name)

    def restart(self, name: Optional[str] = None) -> bool:
        """
        Restarts a WSL2 distribution.
        """
        if not name or not self.exists(name):
            return False
        try:
            self.stop(name)
            self.start(name)
            return True
        except Exception:
            return False

    def get_flavors(self) -> List[Dict[str, Any]]:
        """
        WSL2 does not have 'flavors' in the cloud sense.
        """
        return [{"name": "standard", "description": "Default WSL2 Resource allocation"}]

    def get_keys(self) -> List[Dict[str, Any]]:
        """
        WSL2 uses local user keys.
        """
        return [{"name": "local-user-key", "path": "~/.ssh/id_rsa"}]

    def get_security_groups(self) -> List[Dict[str, Any]]:
        """
        WSL2 uses host firewall/networking.
        """
        return [{"name": "default", "description": "Host network access"}]

    def link_ssh_dir(self, name: Optional[str] = None) -> bool:
        """
        Creates a symbolic link from the WSL2 home .ssh directory
        to the host OS's .ssh directory.
        """
        if not name or not self.exists(name):
            self.print("Error: Valid distro name is required to link SSH directory.")
            return False

        cloud_config = self.get_cloud_config("wsl2")
        wsl_user = cloud_config.get("wsl_username")
        host_user = cloud_config.get("host_username")

        if not wsl_user or not host_user:
            self.print("Error: 'wsl_username' and 'host_username' must be configured in clouds.yaml to link SSH directory.")
            return False

        host_ssh_path = f"/mnt/c/Users/{host_user}/.ssh"
        wsl_ssh_path = f"/home/{wsl_user}/.ssh"

        try:
            shell_command = f"rm -rf {wsl_ssh_path} && ln -s {host_ssh_path} {wsl_ssh_path}"
            self._run_command([self._wsl_command(), "-d", name, "-u", "root", "sh", "-c", shell_command])
            return True
        except Exception:
            return False

    def run_command(self, name: str, cmd: str) -> str:
        """
        Executes a command on the WSL2 distribution.
        """
        if not name or not self.exists(name):
            raise VMProviderError(f"VM {name} not found.")

        cloud_config = self.get_cloud_config("wsl2")
        wsl_user = cloud_config.get("wsl_username", "root")

        try:
            result = self._run_command([self._wsl_command(), "-d", name, "-u", wsl_user, "sh", "-c", cmd])
            return result.stdout
        except Exception as e:
            return f"Error executing command: {e}"

    def info(self, name: str) -> Dict[str, Any]:
        """Gets detailed information about a WSL2 distribution."""
        if not name or not self.exists(name):
            raise VMResourceError(f"Distribution {name} not found")
        try:
            result = self._run_command([self._wsl_command(), "--list", "--verbose"])
            for line in self._normalize_wsl_output(result.stdout).splitlines():
                if name in line:
                    return {"RawInfo": line.strip()}
            raise VMResourceError(f"Distribution {name} not found in list")
        except VMResourceError:
            raise
        except Exception as e:
            raise VMProviderError(f"Error getting info for distribution {name}: {e}")

    @property
    def version(self) -> List[str]:
        """
        Returns a list of version strings for the WSL tool.
        """
        try:
            result = self._run_command([self._wsl_command(), "--version"])
            lines = self._normalize_wsl_output(result.stdout).strip().splitlines()
            return [line.strip() for line in lines if ":" in line]
        except Exception:
            pass
        return ["Unknown"]

    def check_requirements(self) -> bool:
        """
        Checks if the requirements for this provider are met on the current system.
        """
        return shutil.which("wsl.exe") is not None or shutil.which("wsl") is not None

    def validate_config(self) -> Dict[str, List[str]]:
        """
        Validates WSL2 configuration.
        """
        errors_map = {}
        config = self.get_cloud_config("wsl2")

        config_name = "Cloudmesh config (~/.config/cloudmesh/clouds.yaml)"
        errors = []
        if not config.get("rootfs"):
            errors.append("Missing required field: 'rootfs' (rootfs image path)")

        if errors:
            errors_map[config_name] = errors

        return errors_map

    def get_provider_info(self) -> Dict[str, Any]:
        """Gets detailed information about the WSL2 provider."""
        return {
            "provider": "WSL2",
            "cloud_name": self.cloud_name,
            "version": self.version,
        }

    def wait_for_status(self, name: str, target_status: str, timeout: int = 300) -> bool:
        """
        Polls the WSL2 VM status until it matches target_status.
        """
        import time
        from cloudmesh.ai.vm.logger import logger

        logger.info(f"Waiting for WSL2 VM {name} to reach status {target_status}...")
        start_time = time.time()

        while time.time() - start_time < timeout:
            vms = self.list()
            vm = next((v for v in vms if v["Name"] == name), None)
            if vm:
                current_status = vm["State"].lower()
                if current_status == target_status.lower():
                    logger.info(f"VM {name} reached status {target_status}.")
                    return True

            time.sleep(5)

        logger.error(f"Timeout reached waiting for WSL2 VM {name} to reach status {target_status}.")
        return False
