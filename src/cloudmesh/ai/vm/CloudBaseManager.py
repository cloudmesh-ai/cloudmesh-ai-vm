from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class CloudBaseManager(ABC):
    """
    Abstract Base Class for Cloud VM Managers.
    All cloud providers (OpenStack, Multipass, etc.) must implement this interface.
    """

    def __init__(self, config: Any):
        self.config = config

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
    def start(self, name: Optional[str] = None) -> str:
        """
        Starts a VM.
        :param name: Optional name for the VM. If not provided, the manager should handle naming.
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

    @abstractmethod
    def get_security_groups(self) -> List[Dict[str, Any]]:
        """
        Lists available security groups for the current cloud.
        :return: A list of security group details.
        """
        pass
