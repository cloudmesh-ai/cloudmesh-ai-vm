from src.LibcloudManager import LibcloudManager

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
        cloud_config = self.config.get("clouds", {}).get("google", {})
        return GCEDriver(
            project_id=cloud_config.get("project_id"),
            private_key=cloud_config.get("private_key")
        )
