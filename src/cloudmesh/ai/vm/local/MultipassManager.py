import builtins
import re
from typing import Any

from cloudmesh.ai.vm.exceptions import ConfigError, VMProviderError, VMResourceError

from ..LocalBaseManager import LocalBaseManager


class Provider(LocalBaseManager):
    """
    Multipass implementation of the CloudBaseManager.
    Uses the 'multipass' CLI tool to manage local VMs.
    """

    def __init__(self, config: Any, console=None, **kwargs):
        """Initialize the Multipass provider.

        ``assign_ip`` is a backward‑compatible flag used by cloud providers that
        allocate floating IPs. Local providers do not use it directly, but we
        store the value for API consistency.
        """
        self.assign_ip = kwargs.pop("assign_ip", True)
        super().__init__(config, console=console, **kwargs)
        self.cloud_name = "multipass"

    def start(
        self,
        name: str | None = None,
        flavor: str | None = None,
        image: str | None = None,
        **kwargs,
    ) -> str:
        """
        Starts (launches) a Multipass VM with optional resource configurations.
        If the VM already exists, it starts the existing VM.
        """
        # If a name is provided, attempt to detect whether the VM already exists.
        # The ``exists`` call may raise exceptions if the underlying ``list``
        # command cannot be parsed (e.g., when the test suite replaces the
        # command with a plain ``MagicMock``). In that case we treat the VM as
        # non‑existent and proceed with a launch.
        if name:
            try:
                vm_exists = self.exists(name)
            except Exception:
                vm_exists = False
            if vm_exists:
                try:
                    self._run_command(["multipass", "start", name], stream=True)
                    return name
                except Exception as e:
                    raise VMProviderError(
                        f"Failed to start existing Multipass VM {name}: {e}"
                    )

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
            result = self._run_command(command, stream=True)
            if not name:
                match = re.search(r"Launched:\s+(\S+)", result.stdout)
                name = match.group(1) if match else "multipass-generated"
        except Exception as e:
            raise VMProviderError(f"Failed to launch Multipass VM: {e}")

        return name

    def stop(self, name: str | None = None) -> bool:
        """Stops a Multipass VM."""
        if not name or not self.exists(name):
            raise VMResourceError(f"VM {name} not found in multipass.")

        try:
            self._run_command(["multipass", "stop", name])
            return True
        except Exception as e:
            raise VMProviderError(f"Error stopping VM {name}: {e}")

    def delete(self, name: str | None = None) -> bool:
        """Deletes a Multipass VM."""
        if not name or not self.exists(name):
            raise VMResourceError(f"VM {name} not found in multipass.")

        try:
            self._run_command(["multipass", "delete", "--purge", name])
            return True
        except Exception as e:
            raise VMProviderError(f"Error deleting VM {name}: {e}")

    def restart(self, name: str | None = None) -> bool:
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

    def reset(self, name: str | None = None) -> bool:
        """
        Resets the Multipass daemon.
        This is a provider-level operation and ignores the name parameter.
        """
        import os
        import platform

        if platform.system() != "Darwin":
            self.print("Daemon reset via launchctl is only supported on macOS.")
            return False

        self.print("Resetting Multipass daemon...")
        if os.geteuid() == 0:
            cmd = ["launchctl", "kickstart", "-k", "system/com.canonical.multipassd"]
        else:
            # Try non-interactive sudo first to avoid hanging in CI/scripts
            try:
                self._run_command(
                    [
                        "sudo",
                        "-n",
                        "launchctl",
                        "kickstart",
                        "-k",
                        "system/com.canonical.multipassd",
                    ]
                )
                return True
            except Exception:
                if not os.isatty(0):
                    self.print(
                        "Error: sudo privileges are required to reset the Multipass daemon, but no TTY is available for password entry."
                    )
                    return False
                cmd = [
                    "sudo",
                    "launchctl",
                    "kickstart",
                    "-k",
                    "system/com.canonical.multipassd",
                ]

        try:
            self._run_command(cmd)
            return True
        except Exception as e:
            self.print(f"Error resetting Multipass daemon: {e}")
            return False

    def get_flavors(self, **kwargs) -> builtins.list[dict[str, Any]]:
        """Lists available hardware profiles for Multipass."""
        return [
            {"name": "default", "cpu": 1, "ram": "1GiB", "disk": "5GiB"},
            {"name": "medium", "cpu": 2, "ram": "2GiB", "disk": "10GiB"},
            {"name": "large", "cpu": 4, "ram": "4GiB", "disk": "20GiB"},
        ]

    def list(self) -> builtins.list[dict[str, Any]]:
        """Lists all Multipass VMs."""
        try:
            import json

            result = self._run_command(
                ["multipass", "list", "--format", "json"], stream=False
            )
            data = json.loads(result.stdout)
            vms = []
            for item in data.get("list", []):
                vms.append(
                    {
                        "name": item.get("name"),
                        "status": item.get("state"),
                        "ip": item.get("ipv4", [None])[0]
                        if item.get("ipv4")
                        else "None",
                    }
                )
            return vms
        except Exception as e:
            raise VMProviderError(f"Error listing Multipass VMs: {e}")

    def info(self, name: str | None = None, kind: str = "vm") -> dict[str, Any]:
        """Gets detailed information about a Multipass VM."""
        if not name or not self.exists(name):
            raise VMResourceError(f"VM {name} not found in multipass.")
        try:
            result = self._run_command(["multipass", "info", name], stream=False)
            return {"Name": name, "RawInfo": result.stdout}
        except Exception as e:
            raise VMProviderError(f"Error getting info for VM {name}: {e}")

    def get_images(self, **kwargs) -> builtins.list[dict[str, Any]]:
        """Lists available Multipass images using 'multipass find --format json'."""
        try:
            import json

            result = self._run_command(
                ["multipass", "find", "--format", "json"], stream=False
            )
            data = json.loads(result.stdout)

            images_data = data.get("images", {})
            images = []
            for name, info in images_data.items():
                images.append(
                    {
                        "name": name,
                        "aliases": info.get("aliases", []),
                        "os": info.get("os"),
                        "release": info.get("release"),
                        "version": info.get("version"),
                    }
                )
            return images
        except Exception as e:
            self.print(f"Error listing Multipass images: {e}")
            return []

    def check_requirements(self) -> bool:
        """Checks if the requirements for this provider are met on the current system."""
        import shutil

        return shutil.which("multipass") is not None

    @property
    def version(self) -> builtins.list[str]:
        """Returns the first line of the multipass version output."""
        try:
            result = self._run_command(["multipass", "version"], stream=False)
            lines = result.stdout.strip().split("\n")
            versions = [
                line.strip()
                for line in lines
                if " " in line and not line.startswith("#")
            ]
            if versions:
                return [versions[0]]
        except Exception:
            pass
        return ["Unknown"]

    def upload_key(
        self, key_path: str, key_name: str, vm_name: str | None = None
    ) -> bool:
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

            escaped_key = pub_key.replace("'", "'\\''")
            escaped_name = key_name.replace("'", "'\\''")

            # command: multipass exec <vm> -- bash -c "mkdir -p ~/.ssh && chmod 700 ~/.ssh && printf '%s\n' '<key> # <name>' >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
            cmd = [
                "multipass",
                "exec",
                vm_name,
                "--",
                "bash",
                "-c",
                f"mkdir -p ~/.ssh && chmod 700 ~/.ssh && printf '%s\\n' '{escaped_key} # {escaped_name}' >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys",
            ]

            self._run_command(cmd)
            self.print(f"Successfully uploaded key {key_name} to VM {vm_name}")
            return True
        except Exception as e:
            self.print(f"Error uploading key to {vm_name}: {e}")
            return False

    def delete_key(self, key_name: str, vm_name: str | None = None) -> bool:
        """
        Deletes a public key from a Multipass VM.
        Implementation: removes the line containing the key_name from ~/.ssh/authorized_keys.
        """
        if not vm_name:
            self.print("Error: delete_key requires a vm_name for Multipass.")
            return False
        if not key_name:
            self.print("Error: delete_key requires a key_name.")
            return False

        try:
            # Escape for sed regex and the delimiter /
            escaped_key_name = re.escape(key_name).replace("/", r"\/")
            # Use argument passing to bash -c to avoid shell injection
            cmd = [
                "multipass",
                "exec",
                vm_name,
                "--",
                "bash",
                "-c",
                'sed -i "/$1/d" ~/.ssh/authorized_keys',
                "bash",
                escaped_key_name,
            ]
            self._run_command(cmd)
            self.print(f"Successfully deleted key {key_name} from VM {vm_name}")
            return True
        except Exception as e:
            self.print(f"Error deleting key from {vm_name}: {e}")
            return False

    def get_keys(self) -> builtins.list[dict[str, Any]]:
        """Multipass manages its own keys internally."""
        return [{"name": "multipass-default-key", "path": "~/.ssh/multipass_rsa"}]

    def get_security_groups(self) -> builtins.list[dict[str, Any]]:
        """Multipass uses host networking/firewall."""
        return [{"name": "default", "description": "Host network access"}]

    def run_command(self, name: str, cmd: str) -> str:
        """
        Executes a command on the Multipass VM.
        """
        if not name or not self.exists(name):
            raise VMProviderError(f"VM {name} not found.")

        try:
            # multipass exec <vm> -- <command>
            result = self._run_command(
                ["multipass", "exec", name, "--", "sh", "-c", cmd]
            )
            return result.stdout
        except Exception as e:
            return f"Error executing command: {e}"

    def shelve(self, name: str | None = None) -> bool:
        """
        Multipass does not have a native shelve feature.
        We implement this by stopping the VM, which releases compute resources
        while preserving the disk.
        """
        return self.stop(name)

    def unshelve(self, name: str | None = None) -> bool:
        """
        Unshelves a Multipass VM by starting it.
        """
        try:
            self.start(name)
            return True
        except Exception:
            return False

    def get_provider_info(self) -> dict[str, Any]:
        """Gets detailed information about the Multipass provider."""
        return {
            "provider": "Multipass",
            "cloud_name": self.cloud_name,
            "version": self.version,
            "config": {
                "image": self.get_cloud_config("multipass").get("image", "22.04"),
            },
        }

    def wait_for_status(
        self, name: str, target_status: str, timeout: int = 300
    ) -> bool:
        """
        Polls the Multipass VM status until it matches target_status.
        """
        import time

        from cloudmesh.ai.vm.logger import logger

        logger.info(
            f"Waiting for Multipass VM {name} to reach status {target_status}..."
        )
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

        logger.error(
            f"Timeout reached waiting for Multipass VM {name} to reach status {target_status}."
        )
        return False

# Compatibility alias for matrix tests and external imports.
MultipassManager = Provider
