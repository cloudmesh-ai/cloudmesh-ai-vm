import subprocess
import json
from typing import List, Dict, Any, Optional
from cloudmesh.ai.vm.CloudBaseManager import CloudBaseManager

class Provider(CloudBaseManager):
    """
    Multipass implementation of the CloudBaseManager.
    Uses the 'multipass' CLI tool to manage local VMs.
    """

    def __init__(self, config: Any, console=None, **kwargs):
        super().__init__(config, console=console, **kwargs)
        self.cloud_name = "multipass"

    def _run_command(self, command: List[str]) -> subprocess.CompletedProcess:
        """Helper to run shell commands and stream output in real-time."""
        try:
            # Use Popen to stream output line by line
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            full_output = []
            for line in process.stdout:
                self.print_ansi(line, end="")
                full_output.append(line)
                
            process.wait()
            
            if process.returncode != 0:
                # Create a CalledProcessError to maintain compatibility with existing error handling
                raise subprocess.CalledProcessError(
                    process.returncode, 
                    command, 
                    output="".join(full_output),
                    stderr="".join(full_output)
                )
                
            return subprocess.CompletedProcess(
                args=command, 
                returncode=process.returncode, 
                stdout="".join(full_output), 
                stderr=None
            )
        except subprocess.CalledProcessError as e:
            # The error is already printed via the loop above, but we keep the exception for the caller
            raise e
        except Exception as e:
            self.print(f"Unexpected error executing command {' '.join(command)}: {e}")
            raise e

    def start(self, name: Optional[str] = None, flavor: Optional[str] = None, image: Optional[str] = None) -> str:
        """
        Launch a new VM, or resume an existing stopped or suspended VM.
        """
        if name:
            existing = next((vm for vm in self.list() if vm["name"] == name), None)
            if existing:
                status = existing["status"].lower()
                if status == "running":
                    return name
                if status in {"stopped", "suspended"}:
                    self._run_interactive(["multipass", "start", name])
                    return name
                raise ValueError(f"Cannot start VM {name} in state {existing['status']}.")

        cloud_config = self.get_cloud_config("multipass")
        
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
        
        self._run_interactive(command)
        
        return name if name else "multipass-generated"

    def stop(self, name: Optional[str] = None) -> bool:
        """Stops a Multipass VM."""
        if not name:
            raise ValueError("VM name is required to stop the VM.")
        
        try:
            self._run_command(["multipass", "stop", name])
            return True
        except Exception as e:
            self.print(f"Error stopping VM {name}: {e}")
            return False

    def delete(self, name: Optional[str] = None) -> bool:
        """Deletes a Multipass VM."""
        if not name:
            raise ValueError("VM name is required to delete the VM.")
        
        try:
            self._run_command(["multipass", "delete", "--purge", name])
            return True
        except Exception as e:
            self.print(f"Error deleting VM {name}: {e}")
            return False

    def restart(self, name: Optional[str] = None) -> bool:
        """Restarts a Multipass VM."""
        if not name:
            return False
        try:
            self._run_command(["multipass", "restart", name])
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

    def suspend(self, name: Optional[str] = None) -> bool:
        """Suspend a VM while retaining its disk and saved machine state."""
        if not name:
            raise ValueError("VM name is required to suspend the VM.")
        try:
            self._run_command(["multipass", "suspend", name])
            return True
        except Exception as e:
            self.print(f"Error suspending VM {name}: {e}")
            return False

    def login(self, name: Optional[str] = None) -> bool:
        """Open the managed guest shell without requiring a user SSH key."""
        if not name:
            raise ValueError("VM name is required to log in.")
        self._run_interactive(["multipass", "shell", name])
        return True

    def run_command(self, name: str, command: str) -> str:
        """Execute a shell command in the guest, never in the host shell."""
        if not name or not command.strip():
            raise ValueError("A VM name and nonempty command are required.")
        result = self._run_command_silent(
            ["multipass", "exec", name, "--", "sh", "-lc", command]
        )
        return result.stdout

    def _json_output(self, command: List[str]) -> Dict[str, Any]:
        result = self._run_command_silent(command)
        data = json.loads(result.stdout)
        if not isinstance(data, dict):
            raise ValueError("Multipass returned an invalid JSON object.")
        errors = [error for error in data.get("errors", []) if error]
        if errors:
            raise RuntimeError("; ".join(str(error) for error in errors))
        return data

    @staticmethod
    def _vm_record(name: str, details: Dict[str, Any]) -> Dict[str, Any]:
        addresses = [ip for ip in details.get("ipv4", []) if ip]
        return {
            **details,
            "name": name,
            "status": details.get("state", "Unknown"),
            "ip": addresses[0] if addresses else None,
            "image": details.get("release") or details.get("image_release"),
        }

    def info(self, name: str) -> Dict[str, Any]:
        """Return native details plus the shared name/status/IP fields."""
        data = self._json_output(["multipass", "info", name, "--format", "json"])
        details = data.get("info", {}).get(name)
        if not isinstance(details, dict):
            raise ValueError(f"No information found for VM '{name}'.")
        return self._vm_record(name, details)

    def get_flavors(self) -> List[Dict[str, Any]]:
        """Lists available hardware profiles for Multipass."""
        return [
            {"name": "default", "cpu": 1, "ram": "1GiB", "disk": "5GiB"},
            {"name": "medium", "cpu": 2, "ram": "2GiB", "disk": "10GiB"},
            {"name": "large", "cpu": 4, "ram": "4GiB", "disk": "20GiB"},
        ]


    def list(self) -> List[Dict[str, Any]]:
        """Lists all Multipass VMs."""
        data = self._json_output(["multipass", "list", "--format", "json"])
        instances = data.get("list")
        if not isinstance(instances, list):
            raise ValueError("Multipass inventory is missing the list field.")
        return [self._vm_record(vm["name"], vm) for vm in instances]

    def _run_command_silent(self, command: List[str]) -> subprocess.CompletedProcess:
        """Helper to run shell commands without printing output to the console."""
        return subprocess.run(command, capture_output=True, text=True, check=True)

    def get_images(self) -> List[Dict[str, Any]]:
        """Lists available Multipass images."""
        data = self._json_output(["multipass", "find", "--format", "json"])
        images = data.get("images")
        if not isinstance(images, dict):
            raise ValueError("Multipass image inventory is missing the images field.")
        return [{"name": name, **details} for name, details in images.items()]

    def check_requirements(self) -> bool:
        """Checks if the requirements for this provider are met on the current system."""
        import shutil
        return shutil.which("multipass") is not None

    @property
    def version(self) -> List[str]:
        """Returns the first line of the multipass version output."""
        try:
            result = self._run_command_silent(["multipass", "version"])
            lines = result.stdout.strip().split("\n")
            versions = [line.strip() for line in lines if " " in line and not line.startswith("#")]
            if versions:
                return [versions[0]]
        except Exception:
            pass
        return ["Unknown"]

    def get_keys(self) -> List[Dict[str, Any]]:
        """Multipass has no user-managed key registry to enumerate."""
        return []

    def get_security_groups(self) -> List[Dict[str, Any]]:
        """Multipass does not expose cloud security-group resources."""
        return []

    def get_cost(self, **kwargs) -> Optional[Any]:
        """Returns the cost information for Multipass."""
        return {"value": 0, "unit": None}
    
    def get_provider_info(self) -> Dict[str, Any]:
        """Gets detailed information about the Multipass provider version."""
        info = {}
        version_result = self._run_command_silent(["multipass", "version"])
        for line in version_result.stdout.strip().split("\n"):
            parts = line.strip().split()
            if len(parts) >= 2:
                info[parts[0]] = parts[1]
        if not info:
            raise ValueError("Multipass did not return version information.")
        return info
