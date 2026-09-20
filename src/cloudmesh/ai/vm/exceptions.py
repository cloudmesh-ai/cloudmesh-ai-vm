class CloudMeshError(Exception):
    """Base exception for all cloudmesh-ai-vm errors."""
    pass

class VMProviderError(CloudMeshError):
    """Exception raised for general provider-related failures."""
    pass

class VMAuthError(VMProviderError):
    """Exception raised when authentication with the cloud provider fails."""
    pass

class VMResourceError(VMProviderError):
    """Exception raised when a requested cloud resource (image, flavor, VM) is not found."""
    pass

class VMNetworkError(VMProviderError):
    """Exception raised for network-related failures, such as SSH timeouts or IP resolution issues."""
    pass

class ConfigError(CloudMeshError):
    """Exception raised for configuration-related issues."""
    pass

class ProviderFeatureNotSupported(VMProviderError):
    """Exception raised when a provider does not support a specific feature."""
    def __init__(self, provider_name: str, feature: str):
        self.provider_name = provider_name
        self.feature = feature
        self.message = f"Provider '{provider_name}' does not support the feature: {feature}"
        super().__init__(self.message)

