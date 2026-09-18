import subprocess
import re
from typing import List, Dict, Any, Optional
from src.CloudBaseManager import CloudBaseManager

class Provider(CloudBaseManager):
    """
    Multipass implementation of the CloudBaseManager.
    Uses the 'multipass' CLI tool to manage local VMs.
    """

    def _run_command(self, command: List[str]) -> subprocess.CompletedProcess:
        """Helper to run shell commands."""
        try:
            return subprocess.run(command, capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error executing command {' '.join(command)}: {e.stderr}")
            raise e

    def start(self, name: Optional[str] = None) -> str:
        """
        Starts (launches) a Multipass VM with optional resource configurations.
        """
        cloud_config = self.config.get("clouds", {}).get("multipass", {})
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
            
        command.append(image)
        
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
