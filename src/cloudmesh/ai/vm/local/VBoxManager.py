import re
from typing import List, Dict, Any, Optional
from ..LocalBaseManager import LocalBaseManager
from cloudmesh.ai.vm.exceptions import VMProviderError, VMResourceError, ConfigError

class Provider(LocalBaseManager):
    """
    VirtualBox implementation of the CloudBaseManager.
    Uses the 'VBoxManage' CLI tool to manage local VMs.
    """

    def start(self, name: Optional[str] = None, flavor: Optional[str] = None, image: Optional[str] = None) -> str:
        """
        Starts a VirtualBox VM.
        Note: VBoxManage does not have a simple 'launch' like Multipass.
        This implementation assumes the VM already exists.
        """
        if not name or not self.exists(name):
            raise VMResourceError(f"VirtualBox VM {name} not found.")

        try:
            # Start the VM in headless mode (no GUI window)
            self._run_command(["VBoxManage", "startvm", name, "--type", "headless"])
            return name
        except Exception as e:
            raise VMProviderError(f"Failed to start VirtualBox VM {name}: {e}")

    def stop(self, name: Optional[str] = None) -> bool:
        """
        Stops a VirtualBox VM.
        """
        if not name or not self.exists(name):
            raise VMResourceError(f"VM {name} not found.")

        try:
            # poweroff is the fastest way to stop. acpishutdown is cleaner but slower.
            self._run_command(["VBoxManage", "controlvm", name, "poweroff"])
            return True
        except Exception as e:
            raise VMProviderError(f"Error stopping VM {name}: {e}")

    def delete(self, name: Optional[str] = None) -> bool:
        """
        Deletes a VirtualBox VM and its registered files.
        """
        if not name or not self.exists(name):
            raise VMResourceError(f"VM {name} not found.")

        try:
            # unregistervm --delete removes the VM from the list and deletes the files on disk
            self._run_command(["VBoxManage", "unregistervm", name, "--delete"])
            return True
        except Exception as e:
            raise VMProviderError(f"Error deleting VM {name}: {e}")

    def list(self) -> List[Dict[str, Any]]:
        """
        Lists VirtualBox VMs.
        """
        try:
            result = self._run_command(["VBoxManage", "list", "vms"])
            lines = result.stdout.strip().split("\n")
            if not lines or lines == ['']:
                return []

            vms = []
            for line in lines:
                # VBoxManage list vms output format: "VM Name" {uuid}
                match = re.match(r'"([^"]+)"\s+\{([^}]+)\}', line)
                if match:
                    vms.append({
                        "name": match.group(1),
                        "uuid": match.group(2)
                    })
            return vms
        except Exception:
            return []

    def login(self, name: Optional[str] = None) -> bool:
        """
        VirtualBox does not provide a built-in shell like 'multipass shell'.
        This method informs the user to use SSH or the GUI.
        """
        if not name:
            self.print("Error: VM name is required to login.")
            return False

        self.print(f"Note: VirtualBox does not have a native shell. Please use SSH to log into {name}.")
        self.print(f"Example: ssh username@{ip_address}")
        return False

    def suspend(self, name: Optional[str] = None) -> bool:
        """
        Suspends a VirtualBox VM (Saves state).
        """
        if not name or not self.exists(name):
            self.print(f"Error: VM {name} not found.")
            return False

        try:
            self._run_command(["VBoxManage", "controlvm", name, "savestate"])
            return True
        except Exception:
            return False

    def restart(self, name: Optional[str] = None) -> bool:
        """
        Restarts a VirtualBox VM.
        """
        if not name or not self.exists(name):
            return False
        try:
            self.stop(name)
            self.start(name)
            return True
        except Exception:
            return False

    def get_flavors(self, **kwargs) -> List[Dict[str, Any]]:
        """
        VirtualBox resources are configured per VM.
        """
        return [{"name": "default", "description": "Customizable in VBoxManage modifyvm"}]

    def get_keys(self) -> List[Dict[str, Any]]:
        """
        VirtualBox doesn't manage SSH keys.
        """
        return [{"name": "local-key", "path": "~/.ssh/id_rsa"}]

    def get_security_groups(self) -> List[Dict[str, Any]]:
        """
        VirtualBox uses Networking Modes (NAT, Bridged, etc.)
        """
        return [{"name": "NAT", "description": "Default VirtualBox NAT network"}]

    @property
    def version(self) -> List[str]:
        """
        Returns a list of version strings for the VBoxManage tool.
        """
        try:
            result = self._run_command(["VBoxManage", "--version"])
            return [result.stdout.strip()]
        except Exception:
            pass
        return ["Unknown"]

    def check_requirements(self) -> bool:
        """
        Checks if the requirements for this provider are met on the current system.
        """
        import shutil
        return shutil.which("VBoxManage") is not None

    def run_command(self, name: str, cmd: str) -> str:
        """
        Executes a command on the VirtualBox VM using guestcontrol.
        Requires Guest Additions.
        """
        if not name or not self.exists(name):
            raise VMProviderError(f"VM {name} not found.")

        cloud_config = self.get_cloud_config("vbox")
        username = cloud_config.get("username", "user")
        password = cloud_config.get("password", "")

        try:
            result = self._run_command([
                "VBoxManage", "guestcontrol", name, "run",
                f"--username={username}",
                f"--password={password}",
                "--exe", "/bin/sh",
                "--args", "-c", cmd
            ])
            return result.stdout
        except Exception as e:
            return f"Error executing command (requires Guest Additions): {e}"

    def info(self, name: str) -> Dict[str, Any]:
        """Gets detailed information about a VirtualBox VM."""
        if not name or not self.exists(name):
            raise VMResourceError(f"VM {name} not found.")
        try:
            result = self._run_command(["VBoxManage", "showvminfo", name])
            return {"Name": name, "RawInfo": result.stdout}
        except Exception as e:
            raise VMProviderError(f"Error getting info for VM {name}: {e}")

    def validate_config(self) -> Dict[str, List[str]]:
        """
        Validates VirtualBox configuration.
        """
        return {}

    def get_provider_info(self) -> Dict[str, Any]:
        """Gets detailed information about the VirtualBox provider."""
        return {
            "provider": "VirtualBox",
            "cloud_name": self.cloud_name,
            "version": self.version,
            "config": {
                "version": "VBoxManage",
            },
        }

    def wait_for_status(self, name: str, target_status: str, timeout: int = 300) -> bool:
        """
        Polls the VirtualBox VM status until it matches target_status.
        """
        import time
        from cloudmesh.ai.vm.logger import logger

        logger.info(f"Waiting for VirtualBox VM {name} to reach status {target_status}...")
        start_time = time.time()

        while time.time() - start_time < timeout:
            # VBoxManage doesn't have a simple 'status' command that returns just the state.
            # We use showvminfo and check the 'State' field.
            try:
                res = self.info(name)
                if "error" not in res:
                    info_text = res.get("RawInfo", "")
                    # Search for "State:   running" or similar in showvminfo output
                    import re
                    match = re.search(r"State:\s+([a-zA-Z]+)", info_text)
                    if match:
                        current_status = match.group(1).lower()
                        if current_status == target_status.lower():
                            logger.info(f"VM {name} reached status {target_status}.")
                            return True
            except Exception:
                pass

            time.sleep(5)

        logger.error(f"Timeout reached waiting for VirtualBox VM {name} to reach status {target_status}.")
        return False
