import subprocess
import re
from typing import List, Dict, Any, Optional
from cloudmesh.ai.vm.CloudBaseManager import CloudBaseManager
from cloudmesh.ai.vm.exceptions import VMProviderError

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
            self.print(f"Error executing command {' '.join(command)}: {e.stderr}")
            raise e

    def start(self, name: Optional[str] = None, flavor: Optional[str] = None, image: Optional[str] = None) -> str:
        """
        Starts a VirtualBox VM.
        Note: VBoxManage does not have a simple 'launch' like Multipass.
        This implementation assumes the VM already exists.
        """
        if not name:
            self.print("Error: VirtualBox requires a specific VM name to start.")
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
            self.print("Error: VM name is required to stop.")
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
            self.print("Error: VM name is required to delete.")
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
            self.print("Error: VM name is required to login.")
            return False
        
        self.print(f"Note: VirtualBox does not have a native shell. Please use SSH to log into {name}.")
        self.print(f"Example: ssh username@{ip_address}")
        return False

    def suspend(self, name: Optional[str] = None) -> bool:
        """
        Suspends a VirtualBox VM (Saves state).
        """
        if not name:
            self.print("Error: VM name is required to suspend.")
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
            self.print("Error: VM name is required to restart.")
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



    @property
    def version(self) -> List[str]:
        """
        Returns a list of version strings for the VBoxManage tool.
        """
        try:
            import subprocess
            result = subprocess.run(["VBoxManage", "--version"], capture_output=True, text=True, check=True)
            return [result.stdout.strip()]
        except Exception:
            pass
        return ["Unknown"]

    def check_requirements(self) -> bool:
        """
        Checks if the requirements for this provider are met on the current system.
        """
        import shutil
        return shutil.which("VBoxManage") is not None

    def run_command(self, name: str, cmd: str) -> str:
        """
        Executes a command on the VirtualBox VM using guestcontrol.
        Requires Guest Additions.
        """
        if not name:
            raise VMProviderError("VM name is required to run command.")
        
        cloud_config = self.get_cloud_config("vbox")
        username = cloud_config.get("username", "user")
        password = cloud_config.get("password", "")
        
        try:
            # VBoxManage guestcontrol <vmname> run --username=<user> --password=<pass> --exe <exe> --args <args>
            result = self._run_command([
                "VBoxManage", "guestcontrol", name, "run",
                f"--username={username}",
                f"--password={password}",
                "--exe", "/bin/sh",
                "--args", "-c", cmd
            ])
            return result.stdout
        except subprocess.CalledProcessError as e:
            return f"Error executing command (requires Guest Additions): {e.stderr}"

    def info(self, name: str) -> Dict[str, Any]:
        """Gets detailed information about a VirtualBox VM."""
        try:
            result = self._run_command(["VBoxManage", "showvminfo", name])
            return {"Name": name, "RawInfo": result.stdout}
        except Exception as e:
            return {"error": str(e)}


    def validate_config(self) -> Dict[str, List[str]]:
        """
        Validates VirtualBox configuration.
        """
        return {}

