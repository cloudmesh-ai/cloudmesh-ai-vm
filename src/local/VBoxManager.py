import subprocess
import re
from typing import List, Dict, Any, Optional
from src.CloudBaseManager import CloudBaseManager

class Provider(CloudBaseManager):
    """
    VirtualBox implementation of the CloudBaseManager.
    Uses the 'VBoxManage' CLI tool to manage local VMs.
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
        Starts a VirtualBox VM.
        Note: VBoxManage does not have a simple 'launch' like Multipass.
        This implementation assumes the VM already exists.
        """
        if not name:
            print("Error: VirtualBox requires a specific VM name to start.")
            return "error"
        
        try:
            # Start the VM in headless mode (no GUI window)
            self._run_command(["VBoxManage", "startvm", name, "--type", "headless"])
            return name
        except subprocess.CalledProcessError:
            return "error"

    def stop(self, name: Optional[str] = None) -> bool:
        """
        Stops a VirtualBox VM.
        """
        if not name:
            print("Error: VM name is required to stop.")
            return False
        
        try:
            # poweroff is the fastest way to stop. acpishutdown is cleaner but slower.
            self._run_command(["VBoxManage", "controlvm", name, "poweroff"])
            return True
        except subprocess.CalledProcessError:
            return False

    def delete(self, name: Optional[str] = None) -> bool:
        """
        Deletes a VirtualBox VM and its registered files.
        """
        if not name:
            print("Error: VM name is required to delete.")
            return False
        
        try:
            # unregistervm --delete removes the VM from the list and deletes the files on disk
            self._run_command(["VBoxManage", "unregistervm", name, "--delete"])
            return True
        except subprocess.CalledProcessError:
            return False

    def list(self) -> List[Dict[str, Any]]:
        """
        Lists VirtualBox VMs.
        """
        try:
            result = self._run_command(["VBoxManage", "list", "vms"])
            lines = result.stdout.strip().split("\n")
            if not lines or lines == ['']:
                return []
            
            vms = []
            for line in lines:
                # VBoxManage list vms output format: "VM Name" {uuid}
                match = re.match(r'"([^"]+)"\s+\{([^}]+)\}', line)
                if match:
                    vms.append({
                        "Name": match.group(1),
                        "UUID": match.group(2)
                    })
            return vms
        except subprocess.CalledProcessError:
            return []

    def login(self, name: Optional[str] = None) -> bool:
        """
        VirtualBox does not provide a built-in shell like 'multipass shell'.
        This method informs the user to use SSH or the GUI.
        """
        if not name:
            print("Error: VM name is required to login.")
            return False
        
        print(f"Note: VirtualBox does not have a native shell. Please use SSH to log into {name}.")
        print(f"Example: ssh username@{ip_address}")
        return False

    def suspend(self, name: Optional[str] = None) -> bool:
        """
        Suspends a VirtualBox VM (Saves state).
        """
        if not name:
            print("Error: VM name is required to suspend.")
            return False
        
        try:
            self._run_command(["VBoxManage", "controlvm", name, "savestate"])
            return True
        except subprocess.CalledProcessError:
            return False

    def restart(self, name: Optional[str] = None) -> bool:
        """
        Restarts a VirtualBox VM.
        """
        if not name:
            print("Error: VM name is required to restart.")
            return False
        
        try:
            self.stop(name)
            self.start(name)
            return True
        except subprocess.CalledProcessError:
            return False

    def get_flavors(self) -> List[Dict[str, Any]]:
        """
        VirtualBox resources are configured per VM.
        """
        return [{"name": "default", "description": "Customizable in VBoxManage modifyvm"}]

    def get_keys(self) -> List[Dict[str, Any]]:
        """
        VirtualBox doesn't manage SSH keys.
        """
        return [{"name": "local-key", "path": "~/.ssh/id_rsa"}]

    def get_security_groups(self) -> List[Dict[str, Any]]:
        """
        VirtualBox uses Networking Modes (NAT, Bridged, etc.)
        """
        return [{"name": "NAT", "description": "Default VirtualBox NAT network"}]
