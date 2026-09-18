class CloudMeshError(Exception):
    """Base exception for all cloudmesh-ai-vm errors."""
    pass

class ProviderError(CloudMeshError):
    """Exception raised for general provider-related failures."""
    pass

class AuthenticationError(ProviderError):
    """Exception raised when authentication with the cloud provider fails."""
    pass

class ResourceNotFoundError(ProviderError):
    """Exception raised when a requested cloud resource (image, flavor, VM) is not found."""
    pass

class ConfigError(CloudMeshError):
    """Exception raised for configuration-related issues."""
    pass
