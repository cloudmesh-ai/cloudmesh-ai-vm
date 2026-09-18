from cloudmesh.ai.vm.LibcloudManager import LibcloudManager

try:
    from libcloud.compute.providers.azure import AzureDriver
except ImportError:
    class AzureDriver: pass

class Provider(LibcloudManager):
    """
    Azure implementation of the LibcloudManager.
    """

    def __init__(self, config):
        super().__init__(config, cloud_name="azure")

    def _get_driver(self):
        cloud_config = self.config.clouds.get("azure", {})
        return AzureDriver(
            tenant_id=getattr(cloud_config, "tenant_id", None),
            subscription_id=getattr(cloud_config, "subscription_id", None),
            client_id=getattr(cloud_config, "client_id", None),
            client_secret=getattr(cloud_config, "client_secret", None)
        )
