import os
import re
from typing import List, Dict, Any, Optional
from ..LocalBaseManager import LocalBaseManager
from cloudmesh.ai.vm.exceptions import VMProviderError, ConfigError, VMResourceError, VMAuthError, VMNetworkError

class Provider(LocalBaseManager):
    """
    Lima implementation of the CloudBaseManager.
    Uses the 'limactl' CLI tool to manage local VMs on macOS.
    """

    def __init__(self, config, **kwargs):
        super().__init__(config, **kwargs)
        self.cloud_name = "lima"
        self._verify_installation()

    def _verify_installation(self):
        """Ensure limactl is installed on the system."""
        try:
            self._run_command(["limactl", "--version"])
        except Exception:
            raise VMProviderError("limactl not found. Please install Lima (brew install lima) to use this provider.")

    def start(self, name: Optional[str] = None, flavor: Optional[str] = None, image: Optional[str] = None) -> str:
        """
        Starts (launches) a Lima VM. Supports built-in templates or custom YAML paths.
        """
        cloud_config = self.get_cloud_config("lima")
        # Use image override if provided, otherwise fallback to config 'template' or default 'ubuntu'
        template = image or cloud_config.get("template", "ubuntu")

        # Name sanitization (underscores to hyphens)
        vm_name = name
        if not vm_name:
            vm_name = "lima-vm"
        vm_name = vm_name.replace("_", "-")

        # Resolve template path if it's a file
        expanded_template = os.path.expanduser(template)
        if os.path.exists(expanded_template):
            template_arg = expanded_template
        else:
            # For built-in templates, Lima expects 'template:name' when using --name
            template_arg = f"template:{template}"

        if self.exists(vm_name):
            # VM exists, just start it
            command = ["limactl", "start", vm_name, "--tty=false"]
        else:
            # VM doesn't exist, create and start it
            command = ["limactl", "start", "--name", vm_name, "--tty=false", template_arg]

        try:
            self._run_command(command, stream=True)
        except Exception as e:
            raise VMProviderError(f"Failed to start Lima VM {vm_name}: {e}")
        return vm_name

    def stop(self, name: Optional[str] = None) -> bool:
        """Stops a Lima VM."""
        if not name or not self.exists(name):
            raise VMResourceError(f"VM {name} not found.")

        try:
            self._run_command(["limactl", "stop", name])
            return True
        except Exception as e:
            raise VMProviderError(f"Failed to stop Lima VM {name}: {e}")

    def delete(self, name: Optional[str] = None) -> bool:
        """Deletes a Lima VM."""
        if not name or not self.exists(name):
            raise VMResourceError(f"VM {name} not found.")

        try:
            # limactl delete usually requires confirmation, use -f for force
            self._run_command(["limactl", "delete", "-f", name], stream=True)
            return True
        except Exception as e:
            raise VMProviderError(f"Failed to delete Lima VM {name}: {e}")

    def list(self) -> List[Dict[str, Any]]:
        """Lists Lima VMs."""
        try:
            result = self._run_command(["limactl", "list"], stream=False)
            lines = result.stdout.strip().split("\n")
            if len(lines) < 2:
                return []

            # Parse headers
            headers = lines[0].split()
            vms = []

            for line in lines[1:]:
                parts = line.split()
                if len(parts) >= 2:
                    # Use lowercase keys for consistency across providers
                    vm_info = {headers[i].lower(): parts[i] for i in range(min(len(headers), len(parts)))}

                    # Normalize keys for ssh_config and other tools
                    name = vm_info.get("name")
                    ip = vm_info.get("ssh") or vm_info.get("ip")

                    vm_info["name"] = name
                    vm_info["ip"] = ip

                    vms.append(vm_info)

            return vms
        except Exception:
            return []

    def info(self, name: str) -> Dict[str, Any]:
        """
        Gets detailed information about a Lima VM.
        """
        if not name or not self.exists(name):
            raise VMResourceError(f"VM {name} not found")

        vms = self.list()
        for vm in vms:
            if vm.get("name") == name:
                return vm
        raise VMResourceError(f"VM {name} not found in list")

    def run_command(self, name: str, cmd: str) -> str:
        """
        Executes a command on a Lima VM.
        """
        if not name or not self.exists(name):
            raise VMProviderError(f"VM {name} not found.")
        try:
            # limactl shell <name> <cmd>
            result = self._run_command(["limactl", "shell", name, "sh", "-c", cmd], stream=False)
            return result.stdout.strip()
        except Exception as e:
            return f"Error executing command: {e}"

    def login(self, name: Optional[str] = None) -> bool:
        """Logs into a Lima VM using 'limactl shell'."""
        if not name:
            self.print("Error: VM name is required to login.")
            return False

        try:
            self._run_command(["limactl", "shell", name])
            return True
        except Exception:
            return False

    def suspend(self, name: Optional[str] = None) -> bool:
        """Lima doesn't have a native 'suspend' in the same way; using 'stop'."""
        return self.stop(name)

    def restart(self, name: Optional[str] = None) -> bool:
        """Restarts a Lima VM."""
        if not name or not self.exists(name):
            return False
        try:
            self.stop(name)
            self._run_command(["limactl", "start", name])
            return True
        except Exception:
            return False

    def get_images(self) -> List[Dict[str, Any]]:
        """
        Lists available images in Lima using 'limactl start --list-templates'.
        """
        try:
            result = self._run_command(["limactl", "start", "--list-templates"], stream=False)
            lines = result.stdout.strip().split("\n")
            if not lines:
                return []

            images = []
            for line in lines:
                line = line.strip()
                if line.startswith("- "):
                    content = line[2:].strip()
                    if content:
                        template_name = content.split()[0]
                        images.append({"name": template_name})

            return images
        except Exception as e:
            self.print(f"Error listing Lima images: {e}")
            return []

    def get_flavors(self) -> List[Dict[str, Any]]:
        """
        Lima uses templates rather than fixed flavors, but provides common resource profiles.
        """
        return [
            {"name": "default", "cpu": 1, "ram": "1GiB", "disk": "5GiB"},
            {"name": "medium", "cpu": 2, "ram": "2GiB", "disk": "10GiB"},
            {"name": "large", "cpu": 4, "ram": "4GiB", "disk": "20GiB"},
        ]

    def get_flavor(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Gets details for a specific flavor by name.
        """
        flavors = self.get_flavors()
        for flavor in flavors:
            if flavor.get("name") == name:
                return flavor
        return None

    @property
    def version(self) -> List[str]:
        """
        Returns a list of version strings for the limactl tool.
        """
        try:
            result = self._run_command(["limactl", "--version"], stream=False)
            return [result.stdout.strip()]
        except Exception:
            pass
        return ["Unknown"]

    def get_keys(self) -> List[Dict[str, Any]]:
        """Lima manages SSH keys automatically."""
        return [{"name": "lima-ssh-key", "path": "~/.ssh/id_rsa"}]

    def get_security_groups(self) -> List[Dict[str, Any]]:
        """Lima uses port forwarding instead of security groups."""
        return [{"name": "default", "description": "Local port forwarding"}]

    def check_requirements(self) -> bool:
        """
        Checks if the requirements for this provider are met on the current system.
        """
        import shutil
        import platform
        if platform.system() not in ["Darwin", "Linux"]:
            return False
        return shutil.which("limactl") is not None

    def validate_config(self) -> Dict[str, List[str]]:
        """
        Validates Lima configuration.
        """
        errors_map = {}
        config = self.get_cloud_config("lima")

        config_name = "Cloudmesh config (~/.config/cloudmesh/clouds.yaml)"
        errors = []
        if not config.get("template"):
            errors.append("Missing required field: 'template'")

        if errors:
            errors_map[config_name] = errors

        return errors_map

    def shelve(self, name: Optional[str] = None) -> bool:
        """
        Shelves a VM. Not supported for Lima.
        """
        self.print(f"Shelve is not supported for the provider Lima")
        return False

    def unshelve(self, name: Optional[str] = None) -> bool:
        """
        Unshelves a VM. Not supported for Lima.
        """
        self.print(f"Unshelve is not supported for the provider Lima")
        return False

    def get_cost(self, **kwargs) -> Optional[Any]:
        """
        Returns the cost information for Lima.
        """
        return {"value": 0, "unit": None}

    def get_provider_info(self) -> Dict[str, Any]:
        """Gets detailed information about the Lima provider."""
        return {
            "provider": "Lima",
            "cloud_name": self.cloud_name,
            "version": self.version,
            "config": {
                "template": self.get_cloud_config("lima").get("template", "ubuntu"),
            },
        }

    def wait_for_status(self, name: str, target_status: str, timeout: int = 300) -> bool:
        """
        Polls the Lima VM status until it matches target_status.
        """
        import time
        from cloudmesh.ai.vm.logger import logger

        logger.info(f"Waiting for Lima VM {name} to reach status {target_status}...")
        start_time = time.time()

        while time.time() - start_time < timeout:
            vms = self.list()
            vm = next((v for v in vms if v.get("name") == name), None)
            if vm:
                # Lima's list() returns lower-case keys. We normalize status.
                current_status = vm.get("status", '').lower()
                if current_status == target_status.lower():
                    logger.info(f"VM {name} reached status {target_status}.")
                    return True

            time.sleep(5)

        logger.error(f"Timeout reached waiting for Lima VM {name} to reach status {target_status}.")
        return False
