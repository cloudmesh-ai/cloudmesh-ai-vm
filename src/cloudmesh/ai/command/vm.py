import click
import yaml
import os
from typing import Any, Dict, Optional

from cloudmesh.ai.vm.state_manager import StateManager
from cloudmesh.ai.vm.factory import factory
from cloudmesh.ai.vm.config_models import GlobalConfig
from cloudmesh.ai.vm.exceptions import CloudMeshError
from cloudmesh.ai.vm.logger import logger

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

# Register providers with the factory
factory.register("multipass", MultipassProvider)
factory.register("lima", LimaProvider)
factory.register("wsl2", Wsl2Provider)
factory.register("vbox", VBoxProvider)
factory.register("jetstream", JetstreamProvider)
factory.register("chameleon", ChameleonProvider)
factory.register("aws", AwsProvider)
factory.register("azure", AzureProvider)
factory.register("google", GoogleProvider)

CONFIG_PATH = os.path.expanduser("~/.config/cloudmesh/clouds.yaml")
state = StateManager(CONFIG_PATH)

class VMContext:
    """Context object to share state and config across CLI commands."""
    def __init__(self):
        self.cloud_override: Optional[str] = None
        self.provider = None

@click.group(name="vm")
@click.option("--cloud", help="Override the default cloud provider")
@click.pass_context
def vm_group(ctx, cloud):
    """VM management commands"""
    ctx.obj = VMContext()
    ctx.obj.cloud_override = cloud

def get_active_provider(ctx):
    """Helper to resolve the provider based on override or default."""
    cloud_name = ctx.obj.cloud_override or state.config.default_cloud
    if not cloud_name:
        raise click.ClickException("No default cloud set. Use 'cmc vm set <cloud>' or --cloud <cloud>.")
    
    try:
        return factory.create(cloud_name, state.config)
    except Exception as e:
        raise click.ClickException(str(e))

@vm_group.command(name="setup")
def setup():
    """Initialize a sample configuration file"""
    sample_config = {
        "username": "cloudmesh_user",
        "counter": 0,
        "default_cloud": "multipass",
        "clouds": {
            "multipass": {
                "image": "ubuntu-22.04"
            },
            "aws": {
                "region": "us-east-1",
                "image": "ami-xxxxxxxxxxxxxxxxx"
            }
        }
    }
    
    if os.path.exists(CONFIG_PATH):
        click.echo(f"Configuration file already exists at {CONFIG_PATH}")
        return

    click.echo("Sample configuration file:")
    click.echo("-" * 20)
    click.echo(yaml.dump(sample_config, default_flow_style=False))
    click.echo("-" * 20)

    if click.confirm("Do you want to save this as your default configuration?"):
        try:
            os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
            with open(CONFIG_PATH, "w") as f:
                yaml.dump(sample_config, f, default_flow_style=False)
            click.echo(f"Configuration saved to {CONFIG_PATH}")
        except Exception as e:
            click.echo(f"Error saving configuration: {e}", err=True)
    else:
        click.echo("Setup cancelled.")


@vm_group.command(name="set")
@click.argument("cloud")
def set_cloud(cloud):
    """Set the default cloud provider"""
    state.config.default_cloud = cloud
    state.save()
    click.echo(f"Default cloud set to: {cloud}")

@vm_group.command()
@click.option("--name", help="Name of the VM")
@click.pass_context
def start(ctx, name):
    """Starts a VM"""
    provider = get_active_provider(ctx)
    
    vm_name = name
    if not vm_name:
        username = state.config.username
        counter = state.increment_counter()
        # Ensure a hyphen between username and counter, and replace underscores in username
        vm_name = f"{username}-{counter}".replace("_", "-")
    
    try:
        result_name = provider.start(name=vm_name)
        state.set_last_vm(result_name)
        click.echo(f"VM {result_name} started successfully.")
    except CloudMeshError as e:
        click.echo(f"Error: {e}", err=True)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        click.echo(f"An unexpected error occurred: {e}", err=True)

@vm_group.command()
@click.option("--name", help="Name of the VM")
@click.pass_context
def stop(ctx, name):
    """Stops a VM"""
    provider = get_active_provider(ctx)
    
    vm_name = name or state.get_last_vm()
    if not vm_name:
        raise click.ClickException("No VM name provided and no last-used VM found.")

    if provider.stop(name=vm_name):
        click.echo(f"VM {vm_name} stopped.")
    else:
        click.echo(f"Failed to stop VM {vm_name}.", err=True)

@vm_group.command()
@click.option("--name", help="Name of the VM")
@click.pass_context
def delete(ctx, name):
    """Deletes a VM"""
    provider = get_active_provider(ctx)
    
    vm_name = name or state.get_last_vm()
    if not vm_name:
        raise click.ClickException("No VM name provided and no last-used VM found.")

    if provider.delete(name=vm_name):
        click.echo(f"VM {vm_name} deleted.")
    else:
        click.echo(f"Failed to delete VM {vm_name}.", err=True)

@vm_group.command()
@click.option("--json", "format_json", is_flag=True, help="Output in JSON")
@click.option("--yaml", "format_yaml", is_flag=True, help="Output in YAML")
@click.option("--csv", "format_csv", is_flag=True, help="Output in CSV")
@click.option("--table", "format_table", is_flag=True, default=True, help="Output in Table")
@click.pass_context
def list_vms(ctx, format_json, format_yaml, format_csv, format_table):
    """Lists VMs"""
    provider = get_active_provider(ctx)
    vms = provider.list()
    
    if not vms:
        click.echo("No VMs found.")
        return

    if format_json:
        import json
        click.echo(json.dumps(vms, indent=2))
    elif format_yaml:
        click.echo(yaml.dump(vms))
    elif format_csv:
        headers = vms[0].keys()
        click.echo(",".join(headers))
        for vm in vms:
            click.echo(",".join(str(v) for v in vm.values()))
    else:
        headers = vms[0].keys()
        header_line = "  ".join(f"{h:<15}" for h in headers)
        click.echo(header_line)
        click.echo("-" * len(header_line))
        for vm in vms:
            click.echo("  ".join(f"{str(v):<15}" for v in vm.values()))

@vm_group.command()
@click.option("--name", help="Name of the VM")
@click.pass_context
def login(ctx, name):
    """Logs into a VM"""
    provider = get_active_provider(ctx)
    
    vm_name = name or state.get_last_vm()
    if not vm_name:
        raise click.ClickException("No VM name provided and no last-used VM found.")

    if provider.login(name=vm_name):
        click.echo(f"Logged into {vm_name}.")
    else:
        click.echo(f"Failed to login to {vm_name}.", err=True)

@vm_group.command()
@click.option("--name", help="Name of the VM")
@click.pass_context
def suspend(ctx, name):
    """Suspends a VM"""
    provider = get_active_provider(ctx)
    
    vm_name = name or state.get_last_vm()
    if not vm_name:
        raise click.ClickException("No VM name provided and no last-used VM found.")

    if provider.suspend(name=vm_name):
        click.echo(f"VM {vm_name} suspended.")
    else:
        click.echo(f"Failed to suspend VM {vm_name}.", err=True)

@vm_group.command()
@click.option("--name", help="Name of the VM")
@click.pass_context
def restart(ctx, name):
    """Restarts a VM"""
    provider = get_active_provider(ctx)
    
    vm_name = name or state.get_last_vm()
    if not vm_name:
        raise click.ClickException("No VM name provided and no last-used VM found.")

    if provider.restart(name=vm_name):
        click.echo(f"VM {vm_name} restarted.")
    else:
        click.echo(f"Failed to restart VM {vm_name}.", err=True)

@vm_group.command()
@click.option("--name", required=True, help="Name of the reservation")
@click.option("--node-type", required=True, help="Type of node (e.g. compute_skylake)")
@click.option("--count", type=int, required=True, help="Number of nodes")
@click.option("--start", help="Start date (YYYY-MM-DD HH:MM)")
@click.option("--end", help="End date (YYYY-MM-DD HH:MM)")
@click.option("--duration", type=int, help="Duration of the lease in days")
@click.pass_context
def reservation(ctx, name, node_type, count, start, end, duration):
    """Creates a reservation in Chameleon Cloud"""
    provider = get_active_provider(ctx)
    
    if not hasattr(provider, "create_reservation"):
        click.echo("Error: Current provider does not support reservations.", err=True)
        return

    if provider.create_reservation(name=name, node_type=node_type, count=count, start_date=start, end_date=end, duration=duration):
        click.echo(f"Reservation {name} created successfully.")
    else:
        click.echo(f"Failed to create reservation {name}.", err=True)

@vm_group.command()
@click.pass_context
def flavors(ctx):
    """Lists available hardware profiles"""
    provider = get_active_provider(ctx)
    flavors = provider.get_flavors()
    if not flavors:
        click.echo("No flavors found or not supported by this provider.")
        return
    
    headers = flavors[0].keys()
    header_line = "  ".join(f"{h:<15}" for h in headers)
    click.echo(header_line)
    click.echo("-" * len(header_line))
    for f in flavors:
        click.echo("  ".join(f"{str(v):<15}" for v in f.values()))

@vm_group.command()
@click.pass_context
def keys(ctx):
    """Lists available SSH keys"""
    provider = get_active_provider(ctx)
    keys = provider.get_keys()
    if not keys:
        click.echo("No keys found or not supported by this provider.")
        return
    
    headers = keys[0].keys()
    header_line = "  ".join(f"{h:<15}" for h in headers)
    click.echo(header_line)
    click.echo("-" * len(header_line))
    for k in keys:
        click.echo("  ".join(f"{str(v):<15}" for v in k.values()))

@vm_group.command()
@click.pass_context
def security_groups(ctx):
    """Lists available security groups"""
    provider = get_active_provider(ctx)
    groups = provider.get_security_groups()
    if not groups:
        click.echo("No security groups found or not supported by this provider.")
        return
    
    headers = groups[0].keys()
    header_line = "  ".join(f"{h:<15}" for h in headers)
    click.echo(header_line)
    click.echo("-" * len(header_line))
    for g in groups:
        click.echo("  ".join(f"{str(v):<15}" for v in g.values()))

@vm_group.command()
@click.pass_context
def ssh_config(ctx):
    """Suggests SSH config entries for existing VMs"""
    provider = get_active_provider(ctx)
    vms = provider.list()
    
    if not vms:
        click.echo("No existing VMs found to generate config for.")
        return
    
    click.echo("\nAdd the following to your ~/.ssh/config:\n")
    for vm in vms:
        name = vm.get("Name")
        ip = vm.get("IP", " <VM_IP>")
        
        click.echo(f"Host {name}")
        click.echo(f"    HostName {ip}")
        click.echo(f"    User {state.config.username}")
        click.echo(f"    IdentityFile ~/.ssh/id_rsa")
        click.echo("")

entry_point = vm_group

def register(cli):
    """Registers the vm command group to the main CLI."""
    cli.add_command(vm_group, name="vm")
