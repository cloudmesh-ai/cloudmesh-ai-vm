import subprocess
import re
from typing import List, Dict, Any, Optional
from cloudmesh.ai.vm.CloudBaseManager import CloudBaseManager

class Provider(CloudBaseManager):
    """
    Multipass implementation of the CloudBaseManager.
    Uses the 'multipass' CLI tool to manage local VMs.
    """

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
                print(line, end="")
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
            print(f"Unexpected error executing command {' '.join(command)}: {e}")
            raise e

    def start(self, name: Optional[str] = None) -> str:
        """
        Starts (launches) a Multipass VM with optional resource configurations.
        """
        cloud_config = self.get_cloud_config("multipass")
        image = cloud_config.get("image", "22.04")
        cpus = cloud_config.get("cpus")
        memory = cloud_config.get("memory")
        disk = cloud_config.get("disk")
        
        command = ["multipass", "launch"]
        
        if cpus:
            command.extend(["-c", str(cpus)])
        if memory:
            command.extend(["-m", str(memory)])
        if disk:
            command.extend(["-d", str(disk)])
            
        if name:
            command.extend(["-n", name])
            
        command.append(str(image))
        
        self._run_command(command)
        
        return name if name else "multipass-generated"


    def stop(self, name: Optional[str] = None) -> bool:
        """
        Stops a Multipass VM.
        """
        if not name:
            print("Error: VM name is required to stop.")
            return False
        
        try:
            self._run_command(["multipass", "stop", name])
            return True
        except subprocess.CalledProcessError:
            return False

    def delete(self, name: Optional[str] = None) -> bool:
        """
        Deletes a Multipass VM.
        """
        if not name:
            print("Error: VM name is required to delete.")
            return False
        
        try:
            # Multipass requires a delete then a purge
            self._run_command(["multipass", "delete", name])
            self._run_command(["multipass", "purge"])
            return True
        except subprocess.CalledProcessError:
            return False

    def list(self) -> List[Dict[str, Any]]:
        """
        Lists Multipass VMs.
        """
        try:
            result = self._run_command(["multipass", "list"])
            lines = result.stdout.strip().split("\n")
            if len(lines) < 2:
                return []
            
            # Parse headers
            headers = lines[0].split()
            vms = []
            
            for line in lines[1:]:
                parts = line.split()
                if len(parts) >= 2:
                    vm_info = {headers[i]: parts[i] for i in range(min(len(headers), len(parts)))}
                    vms.append(vm_info)
            
            return vms
        except subprocess.CalledProcessError:
            return []

    def login(self, name: Optional[str] = None) -> bool:
        """
        Logs into a Multipass VM using 'multipass shell'.
        """
        if not name:
            print("Error: VM name is required to login.")
            return False
        
        try:
            # 'shell' is interactive, so we use subprocess.run without capture_output
            # to let the user interact with the VM.
            subprocess.run(["multipass", "shell", name], check=True)
            return True
        except subprocess.CalledProcessError:
            return False

    def suspend(self, name: Optional[str] = None) -> bool:
        """
        Multipass does not have a native 'suspend'. Implementing as 'stop'.
        """
        return self.stop(name)

    def restart(self, name: Optional[str] = None) -> bool:
        """
        Restarts a Multipass VM.
        """
        if not name:
            print("Error: VM name is required to restart.")
            return False
        
        try:
            self.stop(name)
            self._run_command(["multipass", "start", name])
            return True
        except subprocess.CalledProcessError:
            return False

        
    def run_command(self, name: str, cmd: str) -> str:
        """
        Executes a command on a Multipass VM.
        """
        try:
            # Use '--' to separate multipass arguments from the command to be executed
            # multipass exec <name> -- sh -c <cmd>
            # Use _run_command_silent to avoid double printing when called from CLI
            result = self._run_command_silent(["multipass", "exec", name, "--", "sh", "-c", cmd])
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            return f"Error executing command: {e.stderr or e.output}"
        except Exception as e:
            return f"Unexpected error: {e}"



    def info(self, name: str) -> Dict[str, Any]:
        """
        Gets detailed information about a Multipass VM.
        """
        try:
            result = self._run_command(["multipass", "info", name])
            lines = result.stdout.strip().split("\n")
            info = {}
            for line in lines:
                if ":" in line:
                    key, value = line.split(":", 1)
                    info[key.strip()] = value.strip()
            return info
        except subprocess.CalledProcessError:
            return {"error": f"Could not get info for VM {name}"}

    def get_flavors(self) -> List[Dict[str, Any]]:
        """
        Multipass uses CPU/RAM/Disk options rather than fixed flavors.
        Returning a list of common custom options.
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

    def _run_command_silent(self, command: List[str]) -> subprocess.CompletedProcess:
        """Helper to run shell commands silently and return the result."""
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True
        )

    def get_images(self) -> List[Dict[str, Any]]:
        """
        Lists available images in Multipass using 'multipass find'.
        """
        try:
            # Use silent command to avoid leaking raw output to console
            result = self._run_command_silent(["multipass", "find"])
            lines = result.stdout.strip().split("\\n")
            if not lines:
                return []
            
            images = []
            # Skip the header line "Available images:" and parse lines starting with "- "
            for line in lines:
                line = line.strip()
                if line.startswith("- "):
                    # Example line: "- 22.04 (Ubuntu Jammy Jellyfish)"
                    # Extract the version string (e.g., 22.04)
                    content = line[2:].strip()
                    if content:
                        image_name = content.split()[0]
                        images.append({"name": image_name})
            
            return images
        except (subprocess.CalledProcessError, Exception) as e:
            print(f"Error listing Multipass images: {e}")
            return []
        
    def check_requirements(self) -> bool:
        """
        Checks if the requirements for this provider are met on the current system.
        """
        import shutil
    @property
    def version(self) -> List[str]:
        """
        Returns the first line of the multipass version output.
        """
        try:
            result = self._run_command_silent(["multipass", "version"])
            # Multipass version output has multiple lines (cli and daemon) and a banner.
            lines = result.stdout.strip().split("\n")
            # We want the lines that look like "multipass 1.x"
            versions = [line.strip() for line in lines if " " in line and not line.startswith("#")]
            if versions:
                return [versions[0]]
        except Exception:
            pass
        return ["Unknown"]

        return shutil.which("multipass") is not None                

    def get_keys(self) -> List[Dict[str, Any]]:
        """
        Multipass manages its own keys internally.
        """
        return [{"name": "multipass-default-key", "path": "~/.ssh/multipass_rsa"}]

    def get_security_groups(self) -> List[Dict[str, Any]]:
        """
        Multipass does not use security groups.
        """
        return [{"name": "default", "description": "Local network access"}]
