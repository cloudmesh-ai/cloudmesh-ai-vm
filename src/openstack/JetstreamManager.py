from src.openstack.OpenstackManager import OpenstackManager

class Provider(OpenstackManager):
    """
    Jetstream implementation of the OpenstackManager.
    """

    def __init__(self, config):
        super().__init__(config, cloud_name="jetstream")
