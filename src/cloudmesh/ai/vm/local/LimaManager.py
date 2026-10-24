import builtins
import os
import re
from typing import Any

from cloudmesh.ai.vm.exceptions import (
    VMProviderError,
    VMResourceError,
)

from ..LocalBaseManager import LocalBaseManager


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
            raise VMProviderError(
                "limactl not found. Please install Lima (brew install lima) to use this provider."
            )

    def start(
        self,
        name: str | None = None,
        flavor: str | None = None,
        image: str | None = None,
        **kwargs,
    ) -> str:
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
            # Use --tty=false to avoid interactive prompts
            command = [
                "limactl",
                "start",
                "--name",
                vm_name,
                "--tty=false",
                template_arg,
            ]

        try:
            self._run_command(command, stream=True)
        except Exception as e:
            raise VMProviderError(f"Failed to start Lima VM {vm_name}: {e}")
        return vm_name

    def stop(self, name: str | None = None) -> bool:
        """Stops a Lima VM."""
        if not name or not self.exists(name):
            raise VMResourceError(f"VM {name} not found.")

        try:
            self._run_command(["limactl", "stop", name])
            return True
        except Exception as e:
            raise VMProviderError(f"Failed to stop Lima VM {name}: {e}")

    def delete(self, name: str | None = None) -> bool:
        """Deletes a Lima VM."""
        if not name:
            raise VMResourceError("No VM name provided for deletion.")
        
        if not self.exists(name):
            # Silently return True if the VM doesn't exist to make pre-cleanup idempotent
            return True

        try:
            # limactl delete usually requires confirmation, use -f for force
            self._run_command(["limactl", "delete", "-f", name], stream=True)
            return True
        except Exception as e:
            raise VMProviderError(f"Failed to delete Lima VM {name}: {e}")

    def list(self) -> list[dict[str, Any]]:
        """Lists Lima VMs."""
        try:
            result = self._run_command(["limactl", "list", "-f", "json"], stream=False)
            import json
            data = json.loads(result.stdout)
            # limactl list -f json returns a list of dicts. Ensure it's a list.
            if isinstance(data, list):
                return data
            return [data] if data else []
        except Exception:
            return []

    def exists(self, name: str) -> bool:
        """Checks if a Lima VM exists."""
        vms = self.list()
        # Handle case where vms might be a list of dicts
        for vm in vms:
            if isinstance(vm, dict) and vm.get("name") == name:
                return True
        return False

    def run(self, name: str, command: str, **kwargs) -> str:
        """Runs a command in a Lima VM."""
        try:
            result = self._run_command(["limactl", "shell", name, command], stream=False)
            return result.stdout
        except Exception as e:
            raise VMProviderError(f"Failed to run command in Lima VM {name}: {e}")

    def get_ssh_config(self, name: str) -> str | None:
        """Generates the SSH config for a Lima VM using limactl show-ssh."""
        try:
            if not self.exists(name):
                return None

            # Use a small retry loop to handle cases where the VM is still initializing
            import time

            for attempt in range(10):
                result = self._run_command(
                    ["limactl", "show-ssh", "--format=config", name],
                    stream=False,
                )
                if result.stdout:
                    return result.stdout.strip()
                time.sleep(5)
            return None
        except Exception:
            return None

    def check_requirements(self) -> bool:
        """
        Checks if the requirements for this provider are met on the current system.
        """
        import platform
        import shutil

        if platform.system() not in ["Darwin", "Linux"]:
            return False
        return shutil.which("limactl") is not None

    def validate_config(self) -> dict[str, builtins.list[str]]:
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

    def shelve(self, name: str | None = None) -> bool:
        """
        Shelves a VM. Not supported for Lima.
        """
        self.print("Shelve is not supported for the provider Lima")
        return False

    def unshelve(self, name: str | None = None) -> bool:
        """
        Unshelves a VM. Not supported for Lima.
        """
        self.print("Unshelve is not supported for the provider Lima")
        return False

    def get_cost(self, **kwargs) -> Any | None:
        """
        Returns the cost information for Lima.
        """
        return {"value": 0, "unit": None}

    def get_provider_info(self) -> dict[str, Any]:
        """Gets detailed information about the Lima provider."""
        return {
            "provider": "Lima",
            "cloud_name": self.cloud_name,
            "version": self.version,
            "config": {
                "template": self.get_cloud_config("lima").get("template", "ubuntu"),
            },
        }

    def wait_for_status(
        self, name: str, target_status: str, timeout: int = 300
    ) -> bool:
        """
        Polls the Lima VM status until it matches target_status.
        """
        import time

        from cloudmesh.ai.vm.logger import logger

        logger.info(f"Waiting for Lima VM {name} to reach status {target_status}...")
        start_time = time.time()

        while time.time() - start_time < timeout:
            vms = self.list()
            vm = next((v for v in vms if isinstance(v, dict) and v.get("name") == name), None)
            if vm:
                # Lima's list() returns lower-case keys. We normalize status.
                current_status = vm.get("status", "").lower()
                if current_status == target_status.lower():
                    logger.info(f"VM {name} reached status {target_status}.")
                    return True

            time.sleep(5)

        logger.error(
            f"Timeout reached waiting for Lima VM {name} to reach status {target_status}."
        )
        return False
