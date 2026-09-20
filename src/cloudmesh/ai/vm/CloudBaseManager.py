from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from rich.text import Text

class CloudBaseManager(ABC):
    """
    Abstract Base Class for Cloud VM Managers.
    All cloud providers (OpenStack, Multipass, etc.) must implement this interface.
    """

    def __init__(self, config: Any, console=None, **kwargs):
        self.config = config
        self.console = console

    def get_cloud_config(self, cloud_name: str) -> Dict[str, Any]:
        """
        Helper to retrieve configuration for a specific cloud, 
        handling both dictionary and GlobalConfig object inputs.
        """
        if isinstance(self.config, dict):
            return self.config.get("clouds", {}).get(cloud_name, {})
        
        # Assume it's a GlobalConfig object (dataclass)
        clouds = getattr(self.config, "clouds", {})
        cloud_cfg = clouds.get(cloud_name, {})
        
        # If the cloud_cfg is a dataclass (ProviderConfig), convert to dict
        if not isinstance(cloud_cfg, dict) and hasattr(cloud_cfg, "__dict__"):
            return cloud_cfg.__dict__
        
        return cloud_cfg if isinstance(cloud_cfg, dict) else {}

    @abstractmethod
    def start(self, name: Optional[str] = None, flavor: Optional[str] = None, image: Optional[str] = None) -> str:
        """
        Starts a VM.
        :param name: Optional name for the VM. If not provided, the manager should handle naming.
        :param flavor: Optional flavor/size override.
        :param image: Optional image override.
        :return: The name of the started VM.
        """
        pass

    @abstractmethod
    def stop(self, name: Optional[str] = None) -> bool:
        """
        Stops a VM.
        :param name: Name of the VM to stop.
        :return: True if successful, False otherwise.
        """
        pass

    @abstractmethod
    def delete(self, name: Optional[str] = None) -> bool:
        """
        Deletes a VM.
        :param name: Name of the VM to delete.
        :return: True if successful, False otherwise.
        """
        pass

    @abstractmethod
    def list(self) -> List[Dict[str, Any]]:
        """
        Lists all VMs managed by this provider.
        :return: A list of dictionaries containing VM details.
        """
        pass

    @abstractmethod
    def login(self, name: Optional[str] = None) -> bool:
        """
        Logs into a VM.
        :param name: Name of the VM to login to.
        :return: True if successful, False otherwise.
        """
        pass

    @abstractmethod
    def suspend(self, name: Optional[str] = None) -> bool:
        """
        Suspends a VM.
        :param name: Name of the VM to suspend.
        :return: True if successful, False otherwise.
        """
        pass

    @abstractmethod
    def shelve(self, name: Optional[str] = None) -> bool:
        """
        Shelves a VM (preserves disk, releases compute resources).
        :param name: Name of the VM to shelve.
        :return: True if successful, False otherwise.
        """
        pass

    @abstractmethod
    def unshelve(self, name: Optional[str] = None) -> bool:
        """
        Unshelves a VM.
        :param name: Name of the VM to unshelve.
        :return: True if successful, False otherwise.
        """
        pass

    @abstractmethod
    def restart(self, name: Optional[str] = None) -> bool:
        """
        Restarts a VM.
        :param name: Name of the VM to restart.
        :return: True if successful, False otherwise.
        """
        pass

    @abstractmethod
    def info(self, name: str) -> Dict[str, Any]:
        """
        Gets detailed information about a specific VM.
        :param name: Name of the VM.
        :return: A dictionary containing VM details.
        """
        pass


    def get_images(self) -> List[Dict[str, Any]]:
        """
        Lists available images for the current cloud.
        :return: A list of image details.
        """
        return []

    def check_requirements(self) -> bool:
        """
        Checks if the requirements for this provider are met on the current system.
        :return: True if requirements are met, False otherwise.
        """
        return True

    @property
    @abstractmethod
    def version(self) -> List[str]:
        """
        Returns a list of version strings for the provider tool or API.
        """
        pass

    @abstractmethod
    def get_flavors(self) -> List[Dict[str, Any]]:
        """
        Lists available flavors/sizes for the current cloud.
        :return: A list of flavor details.
        """
        pass

    @abstractmethod
    def get_keys(self) -> List[Dict[str, Any]]:
        """
        Lists available SSH keys for the current cloud.
        :return: A list of key details.
        """
        pass

    @abstractmethod
    def run_command(self, name: str, cmd: str) -> str:
        """
        Executes a command on the VM.
        :param name: Name of the VM.
        :param cmd: The command to execute.
        :return: The output of the command.
        """
        pass

    def get_security_groups(self) -> List[Dict[str, Any]]:
        """
        Lists available security groups for the current cloud.
        :return: A list of security group details.
        """
        return []

    def upload_key(self, key_path: str, key_name: str) -> bool:
        """
        Uploads a public key to the cloud provider.
        :param key_path: Path to the public key file.
        :param key_name: Name to assign to the key.
        :return: True if successful, False otherwise.
        """
        return False

    def delete_key(self, key_name: str) -> bool:
        """
        Deletes a public key from the cloud provider.
        :param key_name: Name of the key to delete.
        :return: True if successful, False otherwise.
        """
        return False


    def get_cost(self, **kwargs) -> Optional[Any]:
        """
        Returns the cost information for the provider.
        Can be a static string, a dictionary with value/unit, or a dynamic calculation.
        :param kwargs: Parameters for cost calculation.
        :return: Cost information as a string, dict, or None if not implemented.
        """
        return None

    def validate_config(self) -> List[str]:
        """
        Validates that the cloud configuration has all required fields.
        :return: A list of missing or invalid configuration fields. If empty, config is valid.
        """
        return []

    def add_security_group_rule(self, group_name: str, port: int, protocol: str = "tcp", cidr: str = "0.0.0.0/0") -> bool:
        """
        Adds a security group rule to allow traffic on a specific port.
        :param group_name: Name of the security group to modify.
        :param port: Port number to open.
        :param protocol: Protocol to use (e.g., 'tcp', 'udp', 'icmp'). Default is 'tcp'.
        :param cidr: CIDR block to allow. Default is '0.0.0.0/0'.
        :return: True if successful, False otherwise.
        """
        return False

    def print(self, *args, **kwargs):
        """Helper to print output using the associated rich console if available."""
        if self.console:
            self.console.print(*args, **kwargs)
        else:
            print(*args, **kwargs)

    def print_ansi(self, text: str, **kwargs):
        """Prints text and cleans up ANSI sequences and CLI spinner artifacts."""
        import re
        
        # 1. Remove repetitive spinner sequences (e.g., /-\|/-\|).
        # If we see 4 or more characters from the spinner set in a row, it's definitely a spinner.
        sanitized_text = re.sub(r'[/\-\\|]{4,}', '', text)
        
        # 2. Remove any remaining carriage returns or cursor moves to prevent line fragmentation.
        sanitized_text = re.sub(r'\r|\x1b\[[0-9]*G|\x1b\[H', '', sanitized_text)
        
        if self.console:
            self.console.print(Text.from_ansi(sanitized_text), **kwargs)
        else:
            print(sanitized_text, **kwargs)




    def _run_interactive(self, command: List[str]):
        """Runs a command directly connected to the terminal for smooth animations."""
        import subprocess
        try:
            return subprocess.run(command, capture_output=False, check=True)
        except subprocess.CalledProcessError as e:
            # The error is already printed by the process to stderr
            raise e
