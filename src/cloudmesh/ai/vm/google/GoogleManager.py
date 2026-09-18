from cloudmesh.ai.vm.LibcloudManager import LibcloudManager

try:
    from libcloud.compute.providers.gce import GCEDriver
except ImportError:
    class GCEDriver: pass

class Provider(LibcloudManager):
    """
    Google Compute Engine implementation of the LibcloudManager.
    """

    def __init__(self, config):
        super().__init__(config, cloud_name="google")

    def _get_driver(self):
        cloud_config = self.config.clouds.get("google", {})
        return GCEDriver(
            project_id=getattr(cloud_config, "project_id", None),
            private_key=getattr(cloud_config, "private_key", None)
        )
