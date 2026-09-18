from typing import Dict, Type, Optional
from src.CloudBaseManager import CloudBaseManager
from cloudmesh.ai.command.config_models import GlobalConfig
from cloudmesh.ai.command.logger import logger

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
    def create(cls, cloud_name: str, config: GlobalConfig) -> CloudBaseManager:
        manager_cls = cls._registry.get(cloud_name)
        if not manager_cls:
            # Fallback to checking if it's a generic libcloud provider
            # In a real system, we might have a default LibcloudManager implementation
            # that handles many providers via config.
            raise ValueError(f"Provider '{cloud_name}' is not registered in the factory.")
        
        # We pass the full config and the specific cloud name
        return manager_cls(config.__dict__, cloud_name)

# The factory is used as a singleton across the app
factory = ProviderFactory()
