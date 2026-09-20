from cloudmesh.ai.vm.openstack.OpenstackManager import OpenstackManager

class Provider(OpenstackManager):
    """
    Jetstream implementation of the OpenstackManager.
    """

    def __init__(self, config, **kwargs):
        super().__init__(config, cloud_name="jetstream", **kwargs)
