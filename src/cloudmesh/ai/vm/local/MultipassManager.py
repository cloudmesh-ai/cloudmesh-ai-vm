import subprocess
import re
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
        Starts (launches) a Multipass VM with optional resource configurations.
        """
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
            self._run_command(["multipass", "delete", name])
            self._run_command(["multipass", "purge"])
            return True
        except Exception as e:
            self.print(f"Error deleting VM {name}: {e}")
            return False

    def list(self) -> List[Dict[str, Any]]:
        """Lists all Multipass VMs."""
        try:
            result = self._run_command_silent(["multipass", "list"])
            lines = result.stdout.strip().split("\n")
            if not lines or len(lines) < 2:
                return []
            
            vms = []
            # Skip the header line
            for line in lines[1:]:
                # Multipass output is usually columns. We split by whitespace.
                parts = re.split(r'\s+', line.strip(), maxsplit=3)
                if len(parts) >= 3:
                    vms.append({
                        "name": parts[0],
                        "status": parts[1],
                        "ip": parts[2] if parts[2] != "-" else "None"
                    })
            return vms
        except (subprocess.CalledProcessError, Exception) as e:
            self.print(f"Error listing Multipass VMs: {e}")
            return []

    def _run_command_silent(self, command: List[str]) -> subprocess.CompletedProcess:
        """Helper to run shell commands without printing output to the console."""
        try:
            return subprocess.run(command, capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            # Log the error but return the process object to allow the caller to handle it
            return e

    def get_images(self) -> List[Dict[str, Any]]:
        """Lists available Multipass images."""
        try:
            result = self._run_command_silent(["multipass", "images"])
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
        except (subprocess.CalledProcessError, Exception) as e:
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
            result = self._run_command_silent(["multipass", "version"])
            lines = result.stdout.strip().split("\n")
            versions = [line.strip() for line in lines if " " in line and not line.startswith("#")]
            if versions:
                return [versions[0]]
        except Exception:
            pass
        return ["Unknown"]

    def get_keys(self) -> List[Dict[str, Any]]:
        """Multipass manages its own keys internally."""
        return [{"name": "multipass-default-key", "path": "~/.ssh/multipass_rsa"}]

    def get_security_groups(self) -> List[Dict[str, Any]]:
        """Multipass does not use security groups."""
        return [{"name": "default", "description": "Local network access"}]

    def get_cost(self, **kwargs) -> Optional[Any]:
        """Returns the cost information for Multipass."""
        return {"value": 0, "unit": None}
    
    def get_provider_info(self) -> Dict[str, Any]:
        """Gets detailed information about the Multipass provider version."""
        info = {}
        try:
            version_result = self._run_command_silent(["multipass", "version"])
            if hasattr(version_result, "stdout") and version_result.stdout:
                for line in version_result.stdout.strip().split("\n"):
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        info[parts[0]] = parts[1]
        except Exception:
            pass
        
        return info

