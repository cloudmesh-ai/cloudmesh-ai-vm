from typing import Dict, Type, Optional, Any
from cloudmesh.ai.vm.CloudBaseManager import CloudBaseManager
from cloudmesh.ai.vm.logger import logger

class ProviderFactory:
    """
    Registry-based factory for creating cloud provider managers.
    """
    _registry: Dict[str, Type[CloudBaseManager]] = {}

    @classmethod
    def register(cls, name: str, manager_cls: Type[CloudBaseManager]):
        cls._registry[name] = manager_cls
        logger.debug(f"Registered provider: {name} -> {manager_cls.__name__}")

    @classmethod
    def create(cls, cloud_name: str, config: Any, console=None) -> CloudBaseManager:
        manager_cls = cls._registry.get(cloud_name)
        if not manager_cls:
            # Fallback to checking if it's a generic libcloud provider
            # In a real system, we might have a default LibcloudManager implementation
            # that handles many providers via config.
            raise ValueError(f"Provider '{cloud_name}' is not registered in the factory.")
        
        # Pass the GlobalConfig object itself, and the console, not its __dict__
        return manager_cls(config, console=console)

# The factory is used as a singleton across the app
factory = ProviderFactory()
