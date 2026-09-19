import click
import yaml
import os
from typing import Any, Dict, Optional
import logging

from rich.console import Console
from rich.table import Table
import rich.box as box

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
@click.option("--debug", is_flag=True, help="Enable debug logging")
@click.pass_context
def vm_group(ctx, cloud, debug):
    """VM management commands"""
    ctx.obj = VMContext()
    ctx.obj.cloud_override = cloud
    if debug:
        logger.setLevel(logging.DEBUG)
        logger.debug(f"Debug mode enabled. Using cloud: {cloud or state.config.default_cloud}")

def get_active_provider(ctx):
    """Helper to resolve the provider based on override or default."""
    cloud_name = ctx.obj.cloud_override or state.config.default_cloud
    if not cloud_name:
        raise click.ClickException("No default cloud set. Use 'cmc vm set <cloud>' or --cloud <cloud>.")
    
    try:
        provider = factory.create(cloud_name, state.config)
        provider.cloud_name = cloud_name
        return provider
    except Exception as e:
        raise click.ClickException(str(e))

@vm_group.command()
def hello():
    """Hello command"""
    click.echo("Hello from vm!")

@vm_group.command()
def providers():
    """Lists all supported VM providers and their status on this system"""
    providers_list = sorted(factory._registry.keys())
    if not providers_list:
        click.echo("No providers registered.")
        return

    # Initialize Rich table
    table = Table(title="Supported VM Providers", box=box.SQUARE, show_lines=True)
    table.add_column("Provider", style="cyan", no_wrap=True)
    table.add_column("Supported", justify="center")
    table.add_column("Enabled", justify="center")
    table.add_column("OS-YAML", justify="center")
    table.add_column("CM-YAML", justify="center")
    table.add_column("Version", style="magenta")
    table.add_column("Reason", style="green")

    import re
    import os
    import yaml

    os_yaml_path = os.path.expanduser("~/.config/openstack/clouds.yaml")
    os_clouds = {}
    if os.path.exists(os_yaml_path):
        try:
            with open(os_yaml_path, 'r') as f:
                data = yaml.safe_load(f) or {}
                os_clouds = data.get("clouds", data)
        except Exception:
            pass

    for p_name in providers_list:
        status = "❌"
        reason = ""
        
        # Check config presence in CloudMesh
        cloud_cfg_obj = state.config.clouds.get(p_name)
        cm_has = "✅" if cloud_cfg_obj is not None else "❌"
        
        # Check presence in OpenStack clouds.yaml
        os_has = "✅" if p_name in os_clouds else "❌"
        
        # Determine Enabled value
        if cloud_cfg_obj is None:
            enabled_val = "⚪"
        else:
            val = getattr(cloud_cfg_obj, "enabled", None)
            if isinstance(val, str):
                is_enabled = val.lower() == "true"
            elif val is None:
                is_enabled = True
            else:
                is_enabled = bool(val)
            enabled_val = "✅" if is_enabled else "❌"
        
        # OpenStack providers MUST have config in either YAML
        if p_name in ["jetstream", "chameleon", "openstack"]:
            if cm_has == "❌" and os_has == "❌":
                version_str = "N/A"
                try:
                    provider = factory.create(p_name, state.config)
                    version_val = provider.version
                    version_str = "\n".join(version_val) if isinstance(version_val, list) else str(version_val)
                except Exception:
                    pass
                table.add_row(p_name, status, enabled_val, os_has, cm_has, version_str, "Missing config in all YAMLs")
                continue

        try:
            # Try to create the provider to check its requirements
            provider = factory.create(p_name, state.config)
            if provider.check_requirements():
                status = "✅"
                reason = "Supported"
                if cm_has == "❌":
                    reason += " (using defaults)"
            else:
                reason = "Requirements not met"
        except TypeError as e:
            err_msg = str(e)
            if "Can't instantiate abstract class" in err_msg:
                methods_match = re.search(r"abstract methods? '([^']+)'", err_msg)
                if not methods_match:
                    methods_match = re.search(r"implementing new methods: ([^.\n]+)", err_msg)
                methods = methods_match.group(1) if methods_match else "unknown"
                reason = f"Not implemented: {methods}"
            else:
                reason = err_msg
        except Exception as e:
            reason = str(e)

        # Get version from provider
        version_str = "N/A"
        try:
            if 'provider' in locals():
                version_val = provider.version
                version_str = "\n".join(version_val) if isinstance(version_val, list) else str(version_val)
        except Exception:
            pass

        # Format reason style
        if "not met" in reason.lower():
            reason = f"[red]{reason}[/red]"
        elif "not implemented" in reason.lower():
            reason = f"[yellow]{reason}[/yellow]"

        table.add_row(p_name, status, enabled_val, os_has, cm_has, version_str, reason)

    # Print the table to the console
    Console().print(table)


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
            },
            "jetstream": {
                "image": "Featured-Minimal-Ubuntu24",
                "flavor": "m3.tiny"
            },
            "chameleon": {
                "image": "CC-Ubuntu24.04",
                "flavor": "m1.small",
                "region": "CHI@TACC"
            }
        }
    }
    

@vm_group.command(name="config")
def config():
    """Display the current cloud configuration file."""
    click.echo(f"Configuration file location: {CONFIG_PATH}\n")
    try:
        with open(CONFIG_PATH, 'r') as f:
            click.echo(f.read())
    except FileNotFoundError:
        click.echo(f"Configuration file not found at {CONFIG_PATH}", err=True)
    except Exception as e:
        click.echo(f"Error reading configuration file: {e}", err=True)

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


@click.group(name="cloud")
def cloud_group():
    """Manage the active cloud provider"""
    pass

@cloud_group.command(name="get")
def get_cloud():
    """Get the current default cloud provider"""
    cloud = state.config.default_cloud
    if not cloud:
        click.echo("No default cloud provider set. Use 'cmc vm cloud set <provider>' to set one.")
    else:
        click.echo(cloud)

def do_set_cloud(cloud):
    """Logic to set the default cloud provider"""
    state.config.default_cloud = cloud
    state.save()
    click.echo(f"Default cloud set to: {cloud}")

@cloud_group.command(name="set")
@click.argument("cloud")
def set_cloud_cmd(cloud):
    """Set the default cloud provider"""
    do_set_cloud(cloud)

vm_group.add_command(cloud_group)

@vm_group.command(name="set")
@click.argument("cloud")
def set_cloud_shorthand(cloud):
    """Set the default cloud provider (shorthand for 'vm cloud set')"""
    do_set_cloud(cloud)

@vm_group.command()
@click.argument("name", required=False)
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

@vm_group.command(name="run")
@click.option("--name", help="Name of the VM")
@click.argument("command")
@click.pass_context
def run(ctx, name, command):
    """Executes a command on a VM"""
    provider = get_active_provider(ctx)
    
    vm_name = name or state.get_last_vm()
    if not vm_name:
        raise click.ClickException("No VM name provided and no last-used VM found.")
        
    output = provider.run_command(vm_name, command)
    click.echo(output)

@vm_group.command()
@click.argument("name", required=False)
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
@click.argument("name")
@click.pass_context
def info(ctx, name):
    """Gets detailed information about a VM"""
    provider = get_active_provider(ctx)
    vm_info = provider.info(name)
    
    if "error" in vm_info:
        click.echo(f"Error: {vm_info['error']}", err=True)
        return
    
    click.echo(f"\nInformation for VM: {name}")
    click.echo("-" * 30)
    for key, value in vm_info.items():
        click.echo(f"{key:<15}: {value}")
    click.echo("-" * 30)

@vm_group.command()
@click.argument("name", required=False)
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

@vm_group.command(name="list")
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
def images(ctx):
    """Lists available images"""
    provider = get_active_provider(ctx)
    images = provider.get_images()
    if not images:
        click.echo(f"No images found or not supported by provider '{provider.cloud_name}'.")
        return
    
    headers = images[0].keys()
    header_line = "  ".join(f"{h:<15}" for h in headers)
    click.echo(header_line)
    click.echo("-" * len(header_line))
    for i in images:
        click.echo("  ".join(f"{str(v):<15}" for v in i.values()))

@vm_group.command()
@click.pass_context
def flavors(ctx):
    """Lists available hardware profiles"""
    provider = get_active_provider(ctx)
    flavors = provider.get_flavors()
    if not flavors:
        click.echo(f"No flavors found or not supported by provider '{provider.cloud_name}'.")
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
        click.echo(f"No keys found or not supported by provider '{provider.cloud_name}'.")
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
        click.echo(f"No security groups found or not supported by provider '{provider.cloud_name}'.")
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
