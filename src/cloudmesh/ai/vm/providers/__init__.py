from typing import Dict, Type, Any
from cloudmesh.ai.vm.local.MultipassManager import Provider as MultipassProvider
from cloudmesh.ai.vm.openstack.OpenstackManager import OpenstackManager

PROVIDER_MAP: Dict[str, Type] = {
    "multipass": MultipassProvider,
    "openstack": OpenstackManager,
}

def register_providers():
    """
    Registers providers. In a real scenario, this might use entry points.
    For now, we use a hardcoded map for the primary providers.
    """
    pass

def get_provider(cloud_name: str):
    """
    Factory function to return a provider instance based on cloud name.
    """
    provider_class = PROVIDER_MAP.get(cloud_name.lower())
    if not provider_class:
        raise ValueError(f"Unsupported cloud provider: {cloud_name}")
    
    # Resolve config from the CLI state
    try:
        from cloudmesh.ai.command.vm._shared.context import state
        if state.config:
            config = state.config.get_cloud_config(cloud_name)
        else:
            config = {}
    except Exception:
        config = {}
    
    # MultipassProvider might not take cloud_name in __init__ if it's only local
    # but OpenstackManager does. We handle both.
    try:
        return provider_class(config=config, cloud_name=cloud_name)
    except TypeError:
        return provider_class(config=config)
