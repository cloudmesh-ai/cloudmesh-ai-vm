import subprocess
import os
from typing import List, Dict, Any, Optional
from cloudmesh.ai.vm.CloudBaseManager import CloudBaseManager
from cloudmesh.ai.vm.exceptions import VMProviderError

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
            raise VMProviderError("limactl not found. Please install Lima (brew install lima) to use this provider.")

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
                self.print_ansi(line, end="")
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
            self.print(f"Unexpected error executing command {' '.join(command)}: {e}")
            raise e


    def _run_command_silent(self, command: List[str]) -> subprocess.CompletedProcess:
        """Helper to run shell commands silently and return the result."""
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True
        )

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

        command = ["limactl", "start", "--name", vm_name, template_arg]
        
        self._run_interactive(command)
        return vm_name

    def stop(self, name: Optional[str] = None) -> bool:
        """Stops a Lima VM."""
        if not name:
            self.print("Error: VM name is required to stop.")
            return False
        
        try:
            self._run_command(["limactl", "stop", name])
            return True
        except subprocess.CalledProcessError:
            return False

    def delete(self, name: Optional[str] = None) -> bool:
        """Deletes a Lima VM."""
        if not name:
            self.print("Error: VM name is required to delete.")
            return False
        
        try:
            # limactl delete usually requires confirmation, use -f for force
            self._run_interactive(["limactl", "delete", "-f", name])
            return True
        except subprocess.CalledProcessError:
            return False

    def list(self) -> List[Dict[str, Any]]:
        """Lists Lima VMs."""
        try:
            result = self._run_command_silent(["limactl", "list"])
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
                    
                    # Normalize keys for ssh_config and other tools
                    # Lima uses NAME and SSH
                    name = vm_info.get("NAME") or vm_info.get("Name")
                    ip = vm_info.get("SSH") or vm_info.get("IP")
                    
                    vm_info["Name"] = name
                    vm_info["IP"] = ip
                    
                    vms.append(vm_info)
            
            return vms

        except subprocess.CalledProcessError:
            return []

    def info(self, name: str) -> Dict[str, Any]:
        """
        Gets detailed information about a Lima VM.
        """
        vms = self.list()
        for vm in vms:
            if vm.get("Name") == name:
                return vm
        return {"error": f"VM {name} not found"}
    
    def run_command(self, name: str, cmd: str) -> str:
        """
        Executes a command on a Lima VM.
        """
        try:
            # limactl shell <name> <cmd>
            # We use sh -c to ensure the command is executed correctly
            # Use _run_command_silent to avoid double printing when called from CLI
            result = self._run_command_silent(["limactl", "shell", name, "sh", "-c", cmd])
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            return f"Error executing command: {e.stderr or e.output}"
        except Exception as e:
            return f"Unexpected error: {e}"

    def login(self, name: Optional[str] = None) -> bool:
        """Logs into a Lima VM using 'limactl shell'."""
        if not name:
            self.print("Error: VM name is required to login.")
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
            self.print("Error: VM name is required to restart.")
            return False
        
        try:
            self.stop(name)
            self._run_command(["limactl", "start", name])
            return True
        except subprocess.CalledProcessError:
            return False
        
    def get_images(self) -> List[Dict[str, Any]]:
        """
        Lists available images in Lima using 'limactl start --list-templates'.
        """
        try:
            # Use silent command to avoid leaking raw output to console
            result = self._run_command_silent(["limactl", "start", "--list-templates"])
            lines = result.stdout.strip().split("\n")
            if not lines:
                return []
            
            images = []
            # Look for lines starting with '- ' which typically indicate templates
            for line in lines:
                line = line.strip()
                if line.startswith("- "):
                    # Example line: "- ubuntu (Ubuntu 22.04 LTS)"
                    content = line[2:].strip()
                    if content:
                        template_name = content.split()[0]
                        images.append({"name": template_name})
            
            return images
        except (subprocess.CalledProcessError, Exception) as e:
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
            result = self._run_command_silent(["limactl", "--version"])
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

    def validate_config(self) -> List[str]:
        """
        Validates Lima configuration.
        """
        errors = []
        config = self.get_cloud_config("lima")
        if not config.get("template"):
            errors.append("Missing required field: 'template'")
        return errors

