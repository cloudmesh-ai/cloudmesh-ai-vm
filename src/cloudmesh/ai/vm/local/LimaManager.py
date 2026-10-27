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
            # For built-in templates, Lima expects 'template:name'
            template_arg = f"template:{template}"

        if self.exists(vm_name):
            # VM exists, just start it
            command = ["limactl", "start", vm_name, "--yes"]
        else:
            # VM doesn't exist, create and start it
            # The correct syntax for creating a named VM from a template is:
            # limactl start --name <vm_name> --yes <template_arg>
            command = [
                "limactl",
                "start",
                "--name",
                vm_name,
                "--yes",
                template_arg,
            ]
        try:
            print(f"DEBUG: Executing limactl start for {vm_name}...", flush=True)
            # Use os.system for the start command to avoid potential buffering/hanging 
            # issues with the internal _run_command wrapper.
            command_str = " ".join(command)
            exit_code = os.system(command_str)
            if exit_code != 0:
                raise VMProviderError(f"limactl start failed with exit code {exit_code}")
        except Exception as e:
            # Extract error message from the exception or its attributes
            error_msg = str(e).lower()
            # Some command runners put the actual output in the exception's stderr attribute
            if hasattr(e, "stderr") and e.stderr:
                error_msg += " " + e.stderr.lower()
            
            # If it failed because it already exists, we can try to just start it
            if "already exists" in error_msg:
                try:
                    # Try to just start the existing VM
                    os.system(f"limactl start {vm_name} --yes")
                except Exception as e2:
                    raise VMProviderError(f"Failed to start existing Lima VM {vm_name}: {e2}")
            else:
                raise VMProviderError(f"Failed to start Lima VM {vm_name}: {e}")
        
        # Save the started VM as the default VM so get_ssh_config() can find it
        self._save_default_vm(vm_name)
        return vm_name
        
        # Wait for the VM to actually reach 'Running' status before returning
        import time
        timeout = 300  # 5 minutes
        start_time = time.time()
        print(f"Waiting for Lima VM {vm_name} to enter Running state...", flush=True)
        while True:
            if time.time() - start_time > timeout:
                raise VMProviderError(f"Timeout waiting for Lima VM {vm_name} to enter Running state")
            
            vms = self.list()
            for vm in vms:
                vm_name_found = vm.get("name")
                vm_status = vm.get("status")
                if vm_name_found == vm_name:
                    print(f"Checking status for {vm_name_found}: {vm_status}", flush=True)
                    if vm_status == "Running":
                        print(f"VM {vm_name_found} is now Running.", flush=True)
                        break
            else:
                # No matching VM found or not Running yet
                time.sleep(5)
                continue
            break

        # Save the started VM as the default VM so get_ssh_config() can find it
        self._save_default_vm(vm_name)
        return vm_name

    def stop(self, name: str | None = None) -> bool:
        """Stops a Lima VM."""
        if not name:
            name = self._get_default_vm(self.cloud_name)
            if not name:
                raise VMResourceError("No VM name provided and no default VM found.")

        if not self.exists(name):
            return True # Idempotent
 
        try:
            self._run_command(["limactl", "stop", name])
            return True
        except Exception as e:
            raise VMProviderError(f"Failed to stop Lima VM {name}: {e}")
 
    def delete(self, name: str | None = None) -> bool:
        """Deletes a Lima VM."""
        if not name:
            name = self._get_default_vm(self.cloud_name)
            if not name:
                raise VMResourceError("No VM name provided and no default VM found.")
        
        if not self.exists(name):
            # Silently return True if the VM doesn't exist to make pre-cleanup idempotent
            return True

        try:
            # Use -f to force deletion without confirmation
            self._run_command(["limactl", "delete", name, "-f"])
            return True
        except Exception as e:
            raise VMProviderError(f"Failed to delete Lima VM {name}: {e}")

    def get_images(self) -> list[dict[str, Any]]:
        """Lists available Lima templates."""
        try:
            # limactl start --list-templates returns a list of templates
            result = self._run_command(["limactl", "start", "--list-templates"], stream=False)
            
            # The output is typically a list of templates, one per line, possibly with descriptions
            # Example:
            # ubuntu
            # alpine
            # docker
            
            images = []
            for line in result.stdout.strip().splitlines():
                if not line:
                    continue
                # Some versions of Lima might have descriptions, we just want the name
                template_name = line.split()[0] if line else ""
                if template_name:
                    images.append({"name": template_name, "description": line.strip()})
            
            return images
        except Exception as e:
            self.print(f"Failed to list Lima templates: {e}")
            return []

        except Exception as e:
            raise VMProviderError(f"Failed to delete Lima VM {name}: {e}")

    def list(self) -> list[dict[str, Any]]:
        """Lists Lima VMs."""
        try:
            result = self._run_command(["limactl", "list", "-f", "json"], stream=False)
            import json
            vms = []
            for line in result.stdout.strip().splitlines():
                if not line: continue
                try:
                    data = json.loads(line)
                    if isinstance(data, dict):
                        vms.append({k.lower(): v for k, v in data.items()})
                    elif isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict):
                                vms.append({k.lower(): v for k, v in item.items()})
                except json.JSONDecodeError:
                    continue
            return vms
        except Exception as e:
            print(f"DEBUG: LimaManager.list - Exception occurred: {e}")
            return []


    def exists(self, name: str) -> bool:
        """Checks if a Lima VM exists."""
        vms = self.list()
        # Handle case where vms might be a list of dicts
        for vm in vms:
            if isinstance(vm, dict):
                vm_name = vm.get("name")
                if vm_name and str(vm_name).lower() == name.lower():
                    return True
        return False
        return False

    def run_command(self, name: str, command: str, **kwargs) -> str:
        """Runs a command in a Lima VM."""
        try:
            result = self._run_command(["limactl", "shell", name, command], stream=False)
            return result.stdout
        except Exception as e:
            raise VMProviderError(f"Failed to run command in Lima VM {name}: {e}")

    def get_ssh_config(self, name: str | None = None) -> str | None:
        """Generates the SSH config for a Lima VM using limactl show-ssh."""
        try:
            if not name:
                # Try to get the last used VM name from state or config
                name = self._get_default_vm(self.cloud_name)
                if not name:
                    return None

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
    def _save_default_vm(self, name: str):
        """Saves the VM name as the last used VM for this cloud."""
        from pathlib import Path
        state_file = Path(
            os.path.expanduser(f"~/.config/cloudmesh/last_vm.{self.cloud_name}")
        )
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(name)


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
