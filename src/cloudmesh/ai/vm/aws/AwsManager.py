from cloudmesh.ai.vm.LibcloudManager import LibcloudManager

try:
    from libcloud.compute.providers.amazoneb import AmazonEC2Driver
except ImportError:
    class AmazonEC2Driver: pass

class Provider(LibcloudManager):
    """
    AWS EC2 implementation of the LibcloudManager.
    """

    def __init__(self, config):
        super().__init__(config, cloud_name="aws")

    def _get_driver(self):
        cloud_config = self.config.clouds.get("aws", {})
        return AmazonEC2Driver(
            access_key=getattr(cloud_config, "access_key", None),
            secret_key=getattr(cloud_config, "secret_key", None),
            region=getattr(cloud_config, "region", "us-east-1")
        )
