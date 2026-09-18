import subprocess
import os
from typing import List, Dict, Any, Optional
from cloudmesh.ai.vm.CloudBaseManager import CloudBaseManager
from cloudmesh.ai.vm.exceptions import ProviderError

class Provider(CloudBaseManager):
    """
    Lima implementation of the CloudBaseManager.
    Uses the 'limactl' CLI tool to manage local VMs on macOS.
    """

    def __init__(self, config):
        super().__init__(config)
        self._verify_installation()

    def _verify_installation(self):
        """Ensure limactl is installed on the system."""
        try:
            subprocess.run(["limactl", "--version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise ProviderError("limactl not found. Please install Lima (brew install lima) to use this provider.")

    def _run_command(self, command: List[str]) -> subprocess.CompletedProcess:
        """Helper to run shell commands and stream output in real-time."""
        try:
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
            raise e
        except Exception as e:
            print(f"Unexpected error executing command {' '.join(command)}: {e}")
            raise e

    def start(self, name: Optional[str] = None) -> str:
        """
        Starts (launches) a Lima VM. Supports built-in templates or custom YAML paths.
        """
        cloud_config = self.config.clouds.get("lima", {})
        template = getattr(cloud_config, "template", "ubuntu")
        
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

        command = ["limactl", "start", "--name", vm_name, template_arg]
        
        self._run_command(command)
        return vm_name

    def stop(self, name: Optional[str] = None) -> bool:
        """Stops a Lima VM."""
        if not name:
            print("Error: VM name is required to stop.")
            return False
        
        try:
            self._run_command(["limactl", "stop", name])
            return True
        except subprocess.CalledProcessError:
            return False

    def delete(self, name: Optional[str] = None) -> bool:
        """Deletes a Lima VM."""
        if not name:
            print("Error: VM name is required to delete.")
            return False
        
        try:
            # limactl delete usually requires confirmation, use -f for force
            self._run_command(["limactl", "delete", "-f", name])
            return True
        except subprocess.CalledProcessError:
            return False

    def list(self) -> List[Dict[str, Any]]:
        """Lists Lima VMs."""
        try:
            result = self._run_command(["limactl", "list"])
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
        """Logs into a Lima VM using 'limactl shell'."""
        if not name:
            print("Error: VM name is required to login.")
            return False
        
        try:
            # Use subprocess.run for interactive shell
            subprocess.run(["limactl", "shell", name], check=True)
            return True
        except subprocess.CalledProcessError:
            return False

    def suspend(self, name: Optional[str] = None) -> bool:
        """Lima doesn't have a native 'suspend' in the same way; using 'stop'."""
        return self.stop(name)

    def restart(self, name: Optional[str] = None) -> bool:
        """Restarts a Lima VM."""
        if not name:
            print("Error: VM name is required to restart.")
            return False
        
        try:
            self.stop(name)
            self._run_command(["limactl", "start", name])
            return True
        except subprocess.CalledProcessError:
            return False

    def get_flavors(self) -> List[Dict[str, Any]]:
        """Lima uses templates rather than flavors."""
        return [
            {"name": "ubuntu", "description": "Ubuntu Linux"},
            {"name": "fedora", "description": "Fedora Linux"},
            {"name": "alpine", "description": "Alpine Linux"},
            {"name": "debian", "description": "Debian Linux"},
        ]

    def get_keys(self) -> List[Dict[str, Any]]:
        """Lima manages SSH keys automatically."""
        return [{"name": "lima-ssh-key", "path": "~/.ssh/id_rsa"}]

    def get_security_groups(self) -> List[Dict[str, Any]]:
        """Lima uses port forwarding instead of security groups."""
        return [{"name": "default", "description": "Local port forwarding"}]
