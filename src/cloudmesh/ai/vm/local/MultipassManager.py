import re
from typing import List, Dict, Any, Optional
from ..LocalBaseManager import LocalBaseManager
from cloudmesh.ai.vm.exceptions import VMProviderError, VMResourceError, ConfigError

class Provider(LocalBaseManager):
    """
    Multipass implementation of the CloudBaseManager.
    Uses the 'multipass' CLI tool to manage local VMs.
    """

    def __init__(self, config: Any, console=None, **kwargs):
        super().__init__(config, console=console, **kwargs)
        self.cloud_name = "multipass"

    def start(self, name: Optional[str] = None, flavor: Optional[str] = None, image: Optional[str] = None) -> str:
        """
        Starts (launches) a Multipass VM with optional resource configurations.
        """
        cloud_config = self.get_cloud_config("multipass")
        if not cloud_config:
            raise ConfigError("Multipass configuration not found in cloud config.")

        # 1. Resolve image
        vm_image = image or cloud_config.get("image", "22.04")

        # 2. Resolve resources (CPU, Memory, Disk)
        cpus = cloud_config.get("cpus")
        memory = cloud_config.get("memory")
        disk = cloud_config.get("disk")

        if flavor:
            flavor_details = self.get_flavor(flavor)
            if flavor_details:
                cpus = flavor_details.get("cpu", cpus)
                memory = flavor_details.get("ram", memory)
                disk = flavor_details.get("disk", disk)

        command = ["multipass", "launch"]

        if cpus:
            command.extend(["-c", str(cpus)])
        if memory:
            command.extend(["-m", str(memory)])
        if disk:
            command.extend(["-d", str(disk)])

        if name:
            command.extend(["-n", name])

        command.append(str(vm_image))

        try:
            self._run_command(command, stream=True)
        except Exception as e:
            raise VMProviderError(f"Failed to launch Multipass VM: {e}")

        return name if name else "multipass-generated"

    def stop(self, name: Optional[str] = None) -> bool:
        """Stops a Multipass VM."""
        if not name or not self.exists(name):
            raise VMResourceError(f"VM {name} not found in multipass.")

        try:
            self._run_command(["multipass", "stop", name])
            return True
        except Exception as e:
            raise VMProviderError(f"Error stopping VM {name}: {e}")

    def delete(self, name: Optional[str] = None) -> bool:
        """Deletes a Multipass VM."""
        if not name or not self.exists(name):
            raise VMResourceError(f"VM {name} not found in multipass.")

        try:
            self._run_command(["multipass", "delete", name])
            self._run_command(["multipass", "purge"])
            return True
        except Exception as e:
            raise VMProviderError(f"Error deleting VM {name}: {e}")

    def restart(self, name: Optional[str] = None) -> bool:
        """Restarts a Multipass VM."""
        if not name or not self.exists(name):
            return False
        try:
            # Stop the VM
            self.stop(name)

            # Start the VM using multipass start (instead of launch)
            command = ["multipass", "start", name]
            self._run_command(command)
            return True
        except Exception as e:
            self.print(f"Error restarting VM {name}: {e}")
            return False

    def reset(self, name: Optional[str] = None) -> bool:
        """
        Resets the Multipass daemon.
        This is a provider-level operation and ignores the name parameter.
        """
        import platform
        if platform.system() != "Darwin":
            self.print("Daemon reset via launchctl is only supported on macOS.")
            return False
        try:
            self.print("Resetting Multipass daemon...")
            # Use sudo to kickstart the Multipass background service on macOS
            self._run_command(["sudo", "launchctl", "kickstart", "-k", "system/com.canonical.multipassd"])
            return True
        except Exception as e:
            self.print(f"Error resetting Multipass daemon: {e}")
            return False

    def get_flavors(self) -> List[Dict[str, Any]]:
        """Lists available hardware profiles for Multipass."""
        return [
            {"name": "default", "cpu": 1, "ram": "1GiB", "disk": "5GiB"},
            {"name": "medium", "cpu": 2, "ram": "2GiB", "disk": "10GiB"},
            {"name": "large", "cpu": 4, "ram": "4GiB", "disk": "20GiB"},
        ]

    def list(self) -> List[Dict[str, Any]]:
        """Lists all Multipass VMs."""
        try:
            result = self._run_command(["multipass", "list"], stream=False)
            lines = result.stdout.strip().splitlines()
            if not lines or len(lines) < 2:
                return []

            vms = []
            # Skip the header line
            for line in lines[1:]:
                # Multipass output is usually columns. We split by whitespace.
                parts = re.split(r'\s+', line.strip(), maxsplit=3)
                if parts and parts[0] == "*":
                    parts = parts[1:]
                if len(parts) >= 3:
                    vms.append({
                        "name": parts[0],
                        "status": parts[1],
                        "ip": parts[2] if parts[2] != "-" else "None"
                    })
            return vms
        except Exception as e:
            raise VMProviderError(f"Error listing Multipass VMs: {e}")

    def info(self, name: str) -> Dict[str, Any]:
        """Gets detailed information about a Multipass VM."""
        if not name or not self.exists(name):
            raise VMResourceError(f"VM {name} not found in multipass.")
        try:
            result = self._run_command(["multipass", "info", name], stream=False)
            return {"Name": name, "RawInfo": result.stdout}
        except Exception as e:
            raise VMProviderError(f"Error getting info for VM {name}: {e}")

    def get_images(self) -> List[Dict[str, Any]]:
        """Lists available Multipass images."""
        try:
            result = self._run_command(["multipass", "images"], stream=False)
            lines = result.stdout.strip().split("\n")
            if not lines:
                return []

            images = []
            # Skip the header line "Available images:" and parse lines starting with "- "
            for line in lines:
                line = line.strip()
                if line.startswith("- "):
                    # Example line: "- 22.04 (Ubuntu Jammy Jellyfish)"
                    content = line[2:].strip()
                    if content:
                        image_name = content.split()[0]
                        images.append({"name": image_name})
            return images
        except Exception as e:
            self.print(f"Error listing Multipass images: {e}")
            return []

    def check_requirements(self) -> bool:
        """Checks if the requirements for this provider are met on the current system."""
        import shutil
        return shutil.which("multipass") is not None

    @property
    def version(self) -> List[str]:
        """Returns the first line of the multipass version output."""
        try:
            result = self._run_command(["multipass", "version"], stream=False)
            lines = result.stdout.strip().split("\n")
            versions = [line.strip() for line in lines if " " in line and not line.startswith("#")]
            if versions:
                return [versions[0]]
        except Exception:
            pass
        return ["Unknown"]

    def upload_key(self, key_path: str, key_name: str, vm_name: Optional[str] = None) -> bool:
        """
        Uploads a public key to a Multipass VM.
        Uses 'multipass exec' to append the key to authorized_keys.
        """
        if not vm_name:
            self.print("Error: upload_key requires a vm_name for Multipass.")
            return False

        try:
            import os
            key_path = os.path.expanduser(key_path)
            if not os.path.exists(key_path):
                self.print(f"Error: Key file not found: {key_path}")
                return False

            with open(key_path, "r") as f:
                pub_key = f.read().strip()

            # command: multipass exec <vm> -- bash -c "mkdir -p ~/.ssh && echo '<key>' >> ~/.ssh/authorized_keys"
            cmd = ["multipass", "exec", vm_name, "--", "bash", "-c",
                   f"mkdir -p ~/.ssh && chmod 700 ~/.ssh && echo '{pub_key}' >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"]

            self._run_command(cmd)
            self.print(f"Successfully uploaded key {key_name} to VM {vm_name}")
            return True
        except Exception as e:
            self.print(f"Error uploading key to {vm_name}: {e}")
            return False

    def delete_key(self, key_name: str, vm_name: Optional[str] = None) -> bool:
        """
        Deletes a public key from a Multipass VM.
        Implementation: removes the line containing the key_name from ~/.ssh/authorized_keys.
        """
        if not vm_name:
            self.print("Error: delete_key requires a vm_name for Multipass.")
            return False

        try:
            # Use sed to remove the line containing the key name/identifier
            cmd = ["multipass", "exec", vm_name, "--", "bash", "-c", f"sed -i '/{key_name}/d' ~/.ssh/authorized_keys"]
            self._run_command(cmd)
            self.print(f"Successfully deleted key {key_name} from VM {vm_name}")
            return True
        except Exception as e:
            self.print(f"Error deleting key from {vm_name}: {e}")
            return False

    def get_keys(self) -> List[Dict[str, Any]]:
        """Multipass manages its own keys internally."""
        return [{"name": "multipass-default-key", "path": "~/.ssh/multipass_rsa"}]

    def run_command(self, name: str, cmd: str) -> str:
        """
        Executes a command on the Multipass VM.
        """
        if not name or not self.exists(name):
            raise VMProviderError(f"VM {name} not found.")

        try:
            # multipass exec <vm> -- <command>
            result = self._run_command(["multipass", "exec", name, "--", "sh", "-c", cmd])
            return result.stdout
        except Exception as e:
            return f"Error executing command: {e}"


    def shelve(self, name: Optional[str] = None) -> bool:
        """
        Multipass does not have a native shelve feature.
        We implement this by stopping the VM, which releases compute resources
        while preserving the disk.
        """
        return self.stop(name)

    def unshelve(self, name: Optional[str] = None) -> bool:
        """
        Unshelves a Multipass VM by starting the existing (stopped) instance.
        start() would run `multipass launch`, which fails because the
        instance already exists.
        """
        if not name or not self.exists(name):
            raise VMResourceError(f"VM {name} not found in multipass.")

        try:
            self._run_command(["multipass", "start", name])
            return True
        except Exception as e:
            raise VMProviderError(f"Error unshelving VM {name}: {e}")

    def get_provider_info(self) -> Dict[str, Any]:
        """Gets detailed information about the Multipass provider."""
        return {
            "provider": "Multipass",
            "cloud_name": self.cloud_name,
            "version": self.version,
            "config": {
                "image": self.get_cloud_config("multipass").get("image", "22.04"),
            },
        }

    def wait_for_status(self, name: str, target_status: str, timeout: int = 300) -> bool:
        """
        Polls the Multipass VM status until it matches target_status.
        """
        import time
        from cloudmesh.ai.vm.logger import logger

        logger.info(f"Waiting for Multipass VM {name} to reach status {target_status}...")
        start_time = time.time()

        while time.time() - start_time < timeout:
            vms = self.list()
            vm = next((v for v in vms if v["name"] == name), None)
            if vm:
                current_status = vm["status"].lower()
                if current_status == target_status.lower():
                    logger.info(f"VM {name} reached status {target_status}.")
                    return True

            time.sleep(5)

        logger.error(f"Timeout reached waiting for Multipass VM {name} to reach status {target_status}.")
        return False
