import os
from cloudmesh.ai.vm.state_manager import StateManager
from cloudmesh.ai.vm.factory import factory
from cloudmesh.ai.vm.local.MultipassManager import Provider as MultipassProvider
from cloudmesh.ai.vm.local.Wsl2Manager import Provider as Wsl2Provider
from cloudmesh.ai.vm.local.VBoxManager import Provider as VBoxProvider
from cloudmesh.ai.vm.openstack.JetstreamManager import Provider as JetstreamProvider
from cloudmesh.ai.vm.openstack.ChameleonManager import Provider as ChameleonProvider
from cloudmesh.ai.vm.aws.AwsManager import Provider as AwsProvider
from cloudmesh.ai.vm.azure.AzureManager import Provider as AzureProvider
from cloudmesh.ai.vm.google.GoogleManager import Provider as GoogleProvider

factory.register("multipass", MultipassProvider)
factory.register("wsl2", Wsl2Provider)
factory.register("vbox", VBoxProvider)
factory.register("jetstream", JetstreamProvider)
factory.register("chameleon", ChameleonProvider)
factory.register("aws", AwsProvider)
factory.register("azure", AzureProvider)
factory.register("google", GoogleProvider)

CONFIG_PATH = os.path.expanduser("~/.config/cloudmesh/clouds.yaml")
state = StateManager(CONFIG_PATH)

try:
    provider = factory.create("multipass", state.config)
    print("Provider created successfully")
    provider.start("test-vm")
    print("VM started successfully")
except Exception as e:
    import traceback
    traceback.print_exc()
