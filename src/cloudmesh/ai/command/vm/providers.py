import click
from rich.table import Table
import rich.box as box
from .context import console, get_active_provider, vm_options
from cloudmesh.ai.vm.factory import factory

# Import providers for registration
from cloudmesh.ai.vm.local.MultipassManager import Provider as MultipassProvider
from cloudmesh.ai.vm.local.LimaManager import Provider as LimaProvider
from cloudmesh.ai.vm.local.Wsl2Manager import Provider as Wsl2Provider
from cloudmesh.ai.vm.local.VBoxManager import Provider as VBoxProvider
from cloudmesh.ai.vm.openstack.JetstreamManager import Provider as JetstreamProvider
from cloudmesh.ai.vm.openstack.ChameleonManager import Provider as ChameleonProvider
from cloudmesh.ai.vm.aws.AwsManager import Provider as AwsProvider
from cloudmesh.ai.vm.azure.AzureManager import Provider as AzureProvider
from cloudmesh.ai.vm.google.GoogleManager import Provider as GoogleProvider

def register_providers():
    """Register all VM providers with the factory"""
    factory.register("multipass", MultipassProvider)
    factory.register("lima", LimaProvider)
    factory.register("wsl2", Wsl2Provider)
    factory.register("vbox", VBoxProvider)
    factory.register("jetstream", JetstreamProvider)
    factory.register("chameleon", ChameleonProvider)
    factory.register("aws", AwsProvider)
    factory.register("azure", AzureProvider)
    factory.register("google", GoogleProvider)

@click.command()
@vm_options
def providers(ctx):
    """Lists all supported VM providers and their status on this system"""
    providers_list = sorted(factory._registry.keys())
    if not providers_list:
        console.print("No providers registered.")
        return

    # Initialize Rich table
    table = Table(title="Supported VM Providers", box=box.SQUARE, show_lines=True)
    table.add_column("Provider", style="cyan", no_wrap=True)
    table.add_column("Supported", justify="center")

    for p_name in providers_list:
        status = "❌"
        reason = ""
        try:
            # Try to create the provider to check if it's supported (config is valid)
            from cloudmesh.ai.vm.state_manager import state
            provider = factory.create(p_name, state.config)
            errors = provider.validate_config()
            if not errors:
                status = "✅"
            else:
                reason = ", ".join(errors)
        except Exception as e:
            reason = str(e)

        table.add_row(p_name, f"{status} {reason}")

    console.print(table)

@click.command()
@vm_options
def list_regions(ctx):
    """Lists available regions for the active cloud provider"""
    provider = get_active_provider(ctx)
    if not hasattr(provider, "list_regions"):
        console.print(f"[bold red]Error: Provider '{provider.cloud_name}' does not support listing regions.[/bold red]")
        return

    regions = provider.list_regions()
    if not regions:
        console.print("No regions found.")
        return

    # Use a table for better presentation
    table = Table(title=f"Regions for {provider.cloud_name}", box=box.SQUARE, show_lines=True)
    
    # Determine columns from the first region's keys
    headers = list(regions[0].keys())
    for header in headers:
        table.add_column(header)
    
    for region in regions:
        row = [str(region.get(h, "")) for h in headers]
        table.add_row(*row)
    
    console.print(table)
