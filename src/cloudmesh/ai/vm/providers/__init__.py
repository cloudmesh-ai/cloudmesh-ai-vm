from typing import Dict, Type, Any

# Move imports inside functions or at the bottom to avoid circular imports
# since OpenstackManager imports from .providers_utils which calls register_providers()

def get_provider_classes():
    """
    Load VM providers independently so optional dependencies belonging to
    one provider do not prevent other providers from being used.
    """
    from importlib import import_module
    import logging

    providers = {
        "multipass": ("cloudmesh.ai.vm.local.MultipassManager", "Provider"),
        "openstack": ("cloudmesh.ai.vm.openstack.OpenstackManager", "OpenstackManager"),
        "jetstream": ("cloudmesh.ai.vm.openstack.OpenstackManager", "OpenstackManager"),
        "chameleon": ("cloudmesh.ai.vm.openstack.ChameleonManager", "Provider"),
        "aws": ("cloudmesh.ai.vm.aws.AwsManager", "Provider"),
        "azure": ("cloudmesh.ai.vm.azure.AzureManager", "Provider"),
        "google": ("cloudmesh.ai.vm.google.GoogleManager", "Provider"),
        "wsl2": ("cloudmesh.ai.vm.local.Wsl2Manager", "Provider"),
        "vbox": ("cloudmesh.ai.vm.local.VBoxManager", "Provider"),
        "lima": ("cloudmesh.ai.vm.local.LimaManager", "Provider"),
    }

    classes = {}
    for name, (module_path, class_name) in providers.items():
        try:
            module = import_module(module_path)
            classes[name] = getattr(module, class_name)
        except ImportError as exc:
            logging.warning("Provider %s unavailable: %s", name, exc)

    return classes

PROVIDER_MAP = get_provider_classes()

PROVIDER_METADATA = {
    "multipass": {"lifecycle": "🟢", "remote_exec": "🟢 (Agent)", "status": "Fully Functional"},
    "lima": {"lifecycle": "🟢", "remote_exec": "🟢 (SSH)", "status": "Fully Functional"},
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
    from cloudmesh.ai.vm.exceptions import VMProviderError

    provider_class = PROVIDER_MAP.get(cloud_name.lower())
    if not provider_class:
        if cloud_name.lower() in PROVIDER_METADATA:
            raise VMProviderError(
                f"Provider {cloud_name} is unavailable. "
                "Check that its optional dependencies are installed."
            )
        raise VMProviderError(f"Unsupported cloud provider: {cloud_name}")

    try:
        from cloudmesh.ai.command.vm._shared.context import state
        if state.config:
            config = state.config
        else:
            config = {}
    except Exception:
        config = {}

    try:
        return provider_class(config=config, cloud_name=cloud_name)
    except Exception as e:
        raise VMProviderError(f"Failed to instantiate provider {provider_class.__name__} for cloud {cloud_name}: {e}") from e
