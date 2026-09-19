import subprocess
import re
from typing import List, Dict, Any, Optional
from cloudmesh.ai.vm.CloudBaseManager import CloudBaseManager
from cloudmesh.ai.vm.exceptions import ProviderError

class Provider(CloudBaseManager):
    """
    WSL2 implementation of the CloudBaseManager.
    Uses the 'wsl.exe' CLI tool to manage Linux distributions.
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
        Starts a WSL2 distribution. 
        If the distribution doesn't exist, it attempts to import it from a rootfs image.
        """
        if not name:
            print("Error: WSL2 requires a specific distribution name to start.")
            return "error"

        # Check if distro already exists
        try:
            list_output = self._run_command(["wsl", "--list"]).stdout
            if name in list_output:
                # Distro exists, just start it
                self._run_command(["wsl", "-d", name])
                return name
        except subprocess.CalledProcessError:
            pass

        # Attempt to import if not exists
        cloud_config = self.get_cloud_config("wsl2")
        rootfs = cloud_config.get("rootfs")
        install_dir = cloud_config.get("install_dir", "C:\\WSL")

        if not rootfs:
            print(f"Error: Rootfs image path not configured in YAML for wsl2. Cannot import {name}.")
            return "error"

        try:
            # wsl --import <Distro> <InstallLocation> <FileName>
            self._run_command(["wsl", "--import", name, install_dir, rootfs])
            self._run_command(["wsl", "-d", name])
            return name
        except subprocess.CalledProcessError:
            return "error"

    def stop(self, name: Optional[str] = None) -> bool:
        """
        Stops (terminates) a WSL2 distribution.
        """
        if not name:
            print("Error: Distro name is required to stop.")
            return False
        
        try:
            self._run_command(["wsl", "--terminate", name])
            return True
        except subprocess.CalledProcessError:
            return False

    def delete(self, name: Optional[str] = None) -> bool:
        """
        Deletes (unregisters) a WSL2 distribution.
        """
        if not name:
            print("Error: Distro name is required to delete.")
            return False
        
        try:
            self._run_command(["wsl", "--unregister", name])
            return True
        except subprocess.CalledProcessError:
            return False

    def list(self) -> List[Dict[str, Any]]:
        """
        Lists WSL2 distributions.
        """
        try:
            result = self._run_command(["wsl", "--list", "--verbose"])
            lines = result.stdout.strip().split("\n")
            if len(lines) < 2:
                return []
            
            # WSL list output usually has headers: NAME STATE VERSION
            # It can be a bit messy with whitespace, so we use regex or split
            vms = []
            for line in lines[1:]:
                # Extract name, state, version
                # Example: Ubuntu  Running  2
                parts = line.split()
                if len(parts) >= 2:
                    vms.append({
                        "Name": parts[0],
                        "State": parts[1],
                        "Version": parts[2] if len(parts) > 2 else "Unknown"
                    })
            return vms
        except subprocess.CalledProcessError:
            return []

    def login(self, name: Optional[str] = None) -> bool:
        """
        Logs into a WSL2 distribution.
        """
        if not name:
            print("Error: Distro name is required to login.")
            return False
        
        try:
            # launch interactive shell
            subprocess.run(["wsl", "-d", name], check=True)
            return True
        except subprocess.CalledProcessError:
            return False

    def suspend(self, name: Optional[str] = None) -> bool:
        """
        WSL2 doesn't have a 'suspend' mode; we use terminate.
        """
        return self.stop(name)

    def restart(self, name: Optional[str] = None) -> bool:
        """
        Restarts a WSL2 distribution.
        """
        if not name:
            print("Error: Distro name is required to restart.")
            return False
        
        try:
            self.stop(name)
            self.start(name)
            return True
        except subprocess.CalledProcessError:
            return False

    def get_flavors(self) -> List[Dict[str, Any]]:
        """
        WSL2 does not have 'flavors' in the cloud sense.
        """
        return [{"name": "standard", "description": "Default WSL2 Resource allocation"}]

    def get_keys(self) -> List[Dict[str, Any]]:
        """
        WSL2 uses local user keys.
        """
        return [{"name": "local-user-key", "path": "~/.ssh/id_rsa"}]

    def get_security_groups(self) -> List[Dict[str, Any]]:
        """
        WSL2 uses host firewall/networking.
        """
        return [{"name": "default", "description": "Host network access"}]

    def link_ssh_dir(self, name: Optional[str] = None) -> bool:
        """
        Creates a symbolic link from the WSL2 home .ssh directory 
        to the host OS's .ssh directory.
        
        Expected config:
        - wsl_username: username inside WSL2
        - host_username: username on the Windows host
        """
        if not name:
            print("Error: Distro name is required to link SSH directory.")
            return False

        cloud_config = self.get_cloud_config("wsl2")
        wsl_user = cloud_config.get("wsl_username")
        host_user = cloud_config.get("host_username")

        if not wsl_user or not host_user:
            print("Error: 'wsl_username' and 'host_username' must be configured in clouds.yaml to link SSH directory.")
            return False

        # Path on host: C:\Users\<host_user>\.ssh -> /mnt/c/Users/<host_user>/.ssh
        host_ssh_path = f"/mnt/c/Users/{host_user}/.ssh"
        # Path in WSL2: /home/<wsl_user>/.ssh
        wsl_ssh_path = f"/home/{wsl_user}/.ssh"

        try:
            # We use -u root to ensure we have permissions to modify the home directory
            # 1. Remove existing .ssh dir/link if it exists
            # 2. Create the symbolic link
            shell_command = f"rm -rf {wsl_ssh_path} && ln -s {host_ssh_path} {wsl_ssh_path}"
            self._run_command(["wsl", "-d", name, "-u", "root", "sh", "-c", shell_command])
            return True
        except subprocess.CalledProcessError:
            return False


    def run_command(self, name: str, cmd: str) -> str:
        """
        Executes a command on the WSL2 distribution.
        """
        if not name:
            raise ProviderError("VM name is required to run command.")
        
        cloud_config = self.get_cloud_config("wsl2")
        wsl_user = cloud_config.get("wsl_username", "root")
        
        try:
            # Use wsl -d <name> -u <user> sh -c <command>
            result = self._run_command(["wsl", "-d", name, "-u", wsl_user, "sh", "-c", cmd])
            return result.stdout
        except subprocess.CalledProcessError as e:
            return f"Error executing command: {e.stderr}"

    def info(self, name: str) -> Dict[str, Any]:
        """Gets detailed information about a WSL2 distribution."""
        try:
            result = self._run_command(["wsl", "--list", "--verbose"])
            for line in result.stdout.splitlines():
                if name in line:
                    return {"RawInfo": line.strip()}
            return {"error": f"Distribution {name} not found"}
        except Exception as e:
            return {"error": str(e)}


    @property
    def version(self) -> List[str]:
        """
        Returns a list of version strings for the WSL tool.
        """
        try:
            import subprocess
            # wsl --version returns multiple lines of version info
            result = subprocess.run(["wsl", "--version"], capture_output=True, text=True, check=True)
            lines = result.stdout.strip().split("\n")
            # Keep lines that look like "Key: Value"
            return [line.strip() for line in lines if ":" in line]
        except Exception:
            pass
        return ["Unknown"]

    def check_requirements(self) -> bool:
        """
        Checks if the requirements for this provider are met on the current system.
        """
        import shutil
        import platform
        if platform.system() != "Windows":
            return False
        return shutil.which("wsl") is not None