from typing import Dict, Type, Any
from cloudmesh.ai.vm.local.MultipassManager import Provider as MultipassProvider
from cloudmesh.ai.vm.openstack.OpenstackManager import OpenstackManager
from cloudmesh.ai.vm.aws.AwsManager import Provider as AwsProvider
from cloudmesh.ai.vm.azure.AzureManager import Provider as AzureProvider
from cloudmesh.ai.vm.google.GoogleManager import Provider as GoogleProvider
from cloudmesh.ai.vm.local.Wsl2Manager import Provider as Wsl2Provider
from cloudmesh.ai.vm.local.VBoxManager import Provider as VBoxProvider
from cloudmesh.ai.vm.local.LimaManager import Provider as LimaProvider

PROVIDER_MAP: Dict[str, Type] = {
    "multipass": MultipassProvider,
    "openstack": OpenstackManager,
    "jetstream": OpenstackManager,
    "chameleon": OpenstackManager,
    "aws": AwsProvider,
    "azure": AzureProvider,
    "google": GoogleProvider,
    "wsl2": Wsl2Provider,
    "vbox": VBoxProvider,
    "lima": LimaProvider,
}

PROVIDER_METADATA = {
    "multipass": {"lifecycle": "🟢", "remote_exec": "🟢 (Agent)", "status": "Fully Functional"},
    "lima": {"lifecycle": "🟢", "remote_exec": "🟢 (Agent)", "status": "Fully Functional"},
    "openstack": {"lifecycle": "🟢", "remote_exec": "🟢 (SSH)", "status": "Fully Functional"},
    "jetstream": {"lifecycle": "🟢", "remote_exec": "🟢 (SSH)", "status": "Fully Functional"},
    "chameleon": {"lifecycle": "🟢", "remote_exec": "🟢 (SSH)", "status": "Fully Functional"},
    "wsl2": {"lifecycle": "🟢", "remote_exec": "🟢 (Direct)", "status": "Fully Functional"},
    "vbox": {"lifecycle": "🟢", "remote_exec": "🟢 (GuestCtrl)", "status": "Fully Functional"},
    "aws": {"lifecycle": "🟢", "remote_exec": "🟢 (SSH)", "status": "Fully Functional (via Libcloud)"},
    "azure": {"lifecycle": "🟢", "remote_exec": "🟢 (SSH)", "status": "Fully Functional (via Libcloud)"},
    "google": {"lifecycle": "🟢", "remote_exec": "🟢 (SSH)", "status": "Fully Functional (via Libcloud)"},
}

def register_providers():
    """
    Registers providers.
    """
    pass

def get_provider(cloud_name: str):
    """
    Factory function to return a provider instance based on cloud name.
    """
    provider_class = PROVIDER_MAP.get(cloud_name.lower())
    if not provider_class:
        raise ValueError(f"Unsupported cloud provider: {cloud_name}")
    
    try:
        from cloudmesh.ai.command.vm._shared.context import state
        if state.config:
            config = state.config.get_cloud_config(cloud_name)
        else:
            config = {}
    except Exception:
        config = {}
    
    try:
        return provider_class(config=config, cloud_name=cloud_name)
    except TypeError:
        return provider_class(config=config)
