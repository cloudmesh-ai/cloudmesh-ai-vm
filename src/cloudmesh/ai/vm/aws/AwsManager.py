from cloudmesh.ai.vm.LibcloudManager import LibcloudManager

try:
    from libcloud.compute.providers.amazon import AmazonEC2Driver
except ImportError:
    class AmazonEC2Driver:
        def __init__(self, *args, **kwargs): pass

class Provider(LibcloudManager):
    """
    AWS EC2 implementation of the LibcloudManager.
    """

    def __init__(self, config):
        super().__init__(config, cloud_name="aws")

    def _get_driver(self):
        cloud_config = self.get_cloud_config("aws")
        return AmazonEC2Driver(
            access_key=cloud_config.get("access_key"),
            secret_key=cloud_config.get("secret_key"),
            region=cloud_config.get("region", "us-east-1")
        )

    @property
    def version(self) -> List[str]:
        """Returns the provider version."""
        try:
            import libcloud
            return [f"libcloud: {libcloud.__version__}"]
        except Exception:
            return ["libcloud: Unknown"]

