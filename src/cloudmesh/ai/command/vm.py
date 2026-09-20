import click
import yaml
import os
from typing import Any, Dict, Optional
import logging

from rich.console import Console
from rich.table import Table
import rich.box as box

console = Console()

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
        self.verbose: bool = False
        self.provider = None

@click.group(name="vm")
@click.option("--cloud", help="Override the default cloud provider")
@click.option("--debug", is_flag=True, help="Enable debug logging")
@click.option("--verbose", is_flag=True, help="Print raw subprocess/SSH commands")
@click.pass_context
def vm_group(ctx, cloud, debug, verbose):
    """VM management commands"""
    ctx.obj = VMContext()
    ctx.obj.cloud_override = cloud
    ctx.obj.verbose = verbose
    if debug:
        logger.setLevel(logging.DEBUG)
        logger.debug(f"Debug mode enabled. Using cloud: {cloud or state.config.default_cloud}")

def get_active_provider(ctx):
    """Helper to resolve the provider based on override or default."""
    cloud_name = ctx.obj.cloud_override or state.config.default_cloud
    if not cloud_name:
        raise click.ClickException("No default cloud set. Use 'cmc vm set <cloud>' or --cloud <cloud>.")
    
    try:
        provider = factory.create(cloud_name, state.config, console=console)
        provider.cloud_name = cloud_name
        provider.verbose = ctx.obj.verbose
        return provider
    except Exception as e:
        raise click.ClickException(str(e))

@vm_group.command()
def providers():
    """Lists all supported VM providers and their status on this system"""
    providers_list = sorted(factory._registry.keys())
    if not providers_list:
        console.print("No providers registered.")
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
    console.print(f"Configuration file location: {CONFIG_PATH}\n")
    try:
        with open(CONFIG_PATH, 'r') as f:
            console.print(f.read())
    except FileNotFoundError:
        console.print(f"[bold red]Configuration file not found at {CONFIG_PATH}[/bold red]", stderr=True)
    except Exception as e:
        console.print(f"[bold red]Error reading configuration file: {e}[/bold red]", stderr=True)

    if os.path.exists(CONFIG_PATH):
        console.print(f"Configuration file already exists at {CONFIG_PATH}")
        return

    console.print("Sample configuration file:")
    console.print("-" * 20)
    console.print(yaml.dump(sample_config, default_flow_style=False))
    console.print("-" * 20)

    if click.confirm("Do you want to save this as your default configuration?"):
        try:
            os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
            with open(CONFIG_PATH, "w") as f:
                yaml.dump(sample_config, f, default_flow_style=False)
            console.print(f"Configuration saved to {CONFIG_PATH}")
        except Exception as e:
            console.print(f"[bold red]Error saving configuration: {e}[/bold red]", stderr=True)
    else:
        console.print("Setup cancelled.")


@click.group(name="cloud")
def cloud_group():
    """Manage the active cloud provider"""
    pass

@cloud_group.command(name="get")
def get_cloud():
    """Get the current default cloud provider"""
    cloud = state.config.default_cloud
    if not cloud:
        console.print("No default cloud provider set. Use 'cmc vm cloud set <provider>' to set one.")
    else:
        console.print(cloud)

def do_set_cloud(cloud):
    """Logic to set the default cloud provider"""
    try:
        # Create a temporary provider to validate the configuration
        provider = factory.create(cloud, state.config)
        errors = provider.validate_config()
        if errors:
            console.print(f"[bold red]Configuration errors for cloud '{cloud}':[/bold red]", stderr=True)
            for err in errors:
                console.print(f"[bold red]  - {err}[/bold red]", stderr=True)
            raise click.ClickException("Cloud configuration is invalid.")
            
        state.config.default_cloud = cloud
        state.save()
        console.print(f"Default cloud set to: {cloud}")
    except Exception as e:
        if isinstance(e, click.ClickException):
            raise e
        raise click.ClickException(f"Could not set default cloud: {e}")

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
@click.option("--flavor", help="Override VM flavor/size")
@click.option("--image", help="Override VM image")
@click.pass_context
def start(ctx, name, flavor, image):
    """Starts a VM"""
    provider = get_active_provider(ctx)
    
    vm_name = name
    if not vm_name:
        username = state.config.username
        counter = state.increment_counter()
        # Ensure a hyphen between username and counter, and replace underscores in username
        vm_name = f"{username}-{counter}".replace("_", "-")
    
    try:
        console.print("[bold green]Starting VM...[/bold green]")
        result_name = provider.start(name=vm_name, flavor=flavor, image=image)
        state.set_last_vm(provider.cloud_name, result_name)
        console.print(f"VM {result_name} started successfully.")
    except CloudMeshError as e:
        console.print(f"Error: {e}", err=True)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        console.print(f"An unexpected error occurred: {e}", err=True)

@vm_group.command(name="run")
@click.option("--name", help="Name of the VM")
@click.argument("command")
@click.pass_context
def run(ctx, name, command):
    """Executes a command on a VM"""
    provider = get_active_provider(ctx)
    
    vm_name = name or state.get_last_vm(provider.cloud_name)
    if not vm_name:
        raise click.ClickException("No VM name provided and no last-used VM found.")
        
    output = provider.run_command(vm_name, command)
    console.print(output)

@vm_group.command()
@click.argument("name", required=False)
@click.pass_context
def stop(ctx, name):
    """Stops a VM"""
    provider = get_active_provider(ctx)
    
    vm_name = name or state.get_last_vm(provider.cloud_name)
    if not vm_name:
        raise click.ClickException("No VM name provided and no last-used VM found.")

    with console.status("[bold yellow]Stopping VM...[/bold yellow]"):
        stopped = provider.stop(name=vm_name)

    if stopped:
        console.print(f"VM {vm_name} stopped.")
    else:
        console.print(f"[bold red]Failed to stop VM {vm_name}.[/bold red]", stderr=True)

@vm_group.command()
@click.argument("name")
@click.pass_context
def info(ctx, name):
    """Gets detailed information about a VM"""
    provider = get_active_provider(ctx)
    vm_info = provider.info(name)
    
    if "error" in vm_info:
        console.print(f"[bold red]Error: {vm_info['error']}[/bold red]", stderr=True)
        return
    
    console.print(f"\nInformation for VM: {name}")
    console.print("-" * 30)
    for key, value in vm_info.items():
        console.print(f"{key:<15}: {value}")
    console.print("-" * 30)

@vm_group.command()
@click.argument("name", required=False)
@click.pass_context
def delete(ctx, name):
    """Deletes a VM"""
    provider = get_active_provider(ctx)
    
    vm_name = name or state.get_last_vm(provider.cloud_name)
    if not vm_name:
        raise click.ClickException("No VM name provided and no last-used VM found.")

    console.print("[bold red]Deleting VM...[/bold red]")
    deleted = provider.delete(name=vm_name)

    if deleted:
        console.print(f"VM {vm_name} deleted.")
    else:
        console.print(f"[bold red]Failed to delete VM {vm_name}.[/bold red]", stderr=True)

@vm_group.group(name="security-group")
def security_group():
    """Manage VM security groups"""
    pass

@security_group.command(name="add")
@click.argument("group")
@click.argument("port", type=int)
@click.option("--protocol", default="tcp", help="Protocol (tcp, udp, icmp)")
@click.option("--cidr", default="0.0.0.0/0", help="CIDR block to allow")
@click.pass_context
def sg_add(ctx, group, port, protocol, cidr):
    """Adds a rule to a security group"""
    provider = get_active_provider(ctx)
    with console.status(f"[bold blue]Adding rule to {group}...[/bold blue]"):
        success = provider.add_security_group_rule(group, port, protocol, cidr)
    
    if success:
        console.print(f"Rule added successfully to {group}: {protocol} port {port} from {cidr}")
    else:
        console.print(f"[bold red]Failed to add rule to {group}.[/bold red]", stderr=True)

@security_group.command(name="list")
@click.pass_context
def sg_list(ctx):
    """Lists security groups"""
    provider = get_active_provider(ctx)
    groups = provider.get_security_groups()
    
    if not groups:
        console.print("No security groups found.")
        return
    
    console.print(f"{'Group Name':<20} {'Description'}")
    console.print("-" * 40)
    for g in groups:
        console.print(f"{g['name']:<20} {g.get('description', '')}")

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
        console.print("No VMs found.")
        return

    if format_json:
        import json
        console.print(json.dumps(vms, indent=2))
    elif format_yaml:
        console.print(yaml.dump(vms))
    elif format_csv:
        headers = vms[0].keys()
        console.print(",".join(headers))
        for vm in vms:
            console.print(",".join(str(v) for v in vm.values()))
    else:
        # Use Rich table for a professional look
        table = Table(title=f"VMs in {provider.cloud_name}", box=box.SQUARE, show_header=True, header_style="bold magenta")
        
        headers = vms[0].keys()
        for h in headers:
            table.add_column(h)
        
        for vm in vms:
            table.add_row(*[str(v) for v in vm.values()])
        
        console.print(table)

@vm_group.command()
@click.option("--name", help="Name of the VM")
@click.pass_context
def login(ctx, name):
    """Logs into a VM"""
    provider = get_active_provider(ctx)
    
    vm_name = name or state.get_last_vm(provider.cloud_name)
    if not vm_name:
        raise click.ClickException("No VM name provided and no last-used VM found.")

    if provider.login(name=vm_name):
        console.print(f"Logged into {vm_name}.")
    else:
        console.print(f"[bold red]Failed to login to {vm_name}.[/bold red]", stderr=True)

@vm_group.command()
@click.option("--name", help="Name of the VM")
@click.pass_context
def suspend(ctx, name):
    """Suspends a VM"""
    provider = get_active_provider(ctx)
    
    vm_name = name or state.get_last_vm(provider.cloud_name)
    if not vm_name:
        raise click.ClickException("No VM name provided and no last-used VM found.")

    if provider.suspend(name=vm_name):
        console.print(f"VM {vm_name} suspended.")
    else:
        console.print(f"[bold red]Failed to suspend VM {vm_name}.[/bold red]", stderr=True)

@vm_group.command()
@click.option("--name", help="Name of the VM")
@click.pass_context
def restart(ctx, name):
    """Restarts a VM"""
    provider = get_active_provider(ctx)
    
    vm_name = name or state.get_last_vm(provider.cloud_name)
    if not vm_name:
        raise click.ClickException("No VM name provided and no last-used VM found.")

    if provider.restart(name=vm_name):
        console.print(f"VM {vm_name} restarted.")
    else:
        console.print(f"[bold red]Failed to restart VM {vm_name}.[/bold red]", stderr=True)

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
        console.print(f"[bold red]Error: Current provider does not support reservations.[/bold red]", stderr=True)
        return

    if provider.create_reservation(name=name, node_type=node_type, count=count, start_date=start, end_date=end, duration=duration):
        console.print(f"Reservation {name} created successfully.")
    else:
        console.print(f"[bold red]Failed to create reservation {name}.[/bold red]", stderr=True)

@vm_group.command()
@click.pass_context
def images(ctx):
    """Lists available images"""
    provider = get_active_provider(ctx)
    images = provider.get_images()
    if not images:
        console.print(f"No images found or not supported by provider '{provider.cloud_name}'.")
        return
    
    # Use Rich table for a professional look
    table = Table(title=f"Available Images in {provider.cloud_name}", box=box.SQUARE, show_header=True, header_style="bold magenta")
    
    headers = images[0].keys()
    for h in headers:
        table.add_column(h)
    
    for i in images:
        table.add_row(*[str(v) for v in i.values()])
    
    console.print(table)

@vm_group.command()
@click.pass_context
def flavors(ctx):
    """Lists available hardware profiles"""
    provider = get_active_provider(ctx)
    flavors = provider.get_flavors()
    if not flavors:
        console.print(f"No flavors found or not supported by provider '{provider.cloud_name}'.")
        return
    
    # Use Rich table for a professional look
    table = Table(title=f"Available Flavors in {provider.cloud_name}", box=box.SQUARE, show_header=True, header_style="bold magenta")
    
    headers = flavors[0].keys()
    for h in headers:
        table.add_column(h)
    
    for f in flavors:
        table.add_row(*[str(v) for v in f.values()])
    
    console.print(table)

@vm_group.command()
@click.pass_context
def keys(ctx):
    """Lists available SSH keys"""
    provider = get_active_provider(ctx)
    keys = provider.get_keys()
    if not keys:
        console.print(f"No keys found or not supported by provider '{provider.cloud_name}'.")
        return
    
    # Use Rich table for a professional look
    table = Table(title=f"SSH Keys in {provider.cloud_name}", box=box.SQUARE, show_header=True, header_style="bold magenta")
    
    headers = keys[0].keys()
    for h in headers:
        table.add_column(h)
    
    for k in keys:
        table.add_row(*[str(v) for v in k.values()])
    
    console.print(table)

@vm_group.command()
@click.pass_context
def security_groups(ctx):
    """Lists available security groups"""
    provider = get_active_provider(ctx)
    groups = provider.get_security_groups()
    if not groups:
        console.print(f"No security groups found or not supported by provider '{provider.cloud_name}'.")
        return
    
    headers = groups[0].keys()
    header_line = "  ".join(f"{h:<15}" for h in headers)
    console.print(header_line)
    console.print("-" * len(header_line))
    for g in groups:
        console.print("  ".join(f"{str(v):<15}" for v in g.values()))

@vm_group.command()
@click.pass_context
def ssh_config(ctx):
    """Suggests SSH config entries for existing VMs"""
    provider = get_active_provider(ctx)
    vms = provider.list()
    
    if not vms:
        console.print("No existing VMs found to generate config for.")
        return
    
    console.print("\nAdd the following to your ~/.ssh/config:\n")
    for vm in vms:
        name = vm.get("Name")
        ip = vm.get("IP", " <VM_IP>")
        
        console.print(f"Host {name}")
        console.print(f"    HostName {ip}")
        console.print(f"    User {state.config.username}")
        console.print(f"    IdentityFile ~/.ssh/id_rsa")
        console.print("")


@vm_group.command()
@click.argument("name")
@click.pass_context
def assign_floating_ip(ctx, name):
    """Assign an available floating IP to the VM"""
    provider = get_active_provider(ctx)
    if not hasattr(provider, "assign_floating_ip"):
        console.print(f"[bold red]Error: Provider '{provider.cloud_name}' does not support floating IP assignment.[/bold red]", stderr=True)
        return

    ip = provider.assign_floating_ip(name)
    if ip:
        console.print(f"Successfully assigned floating IP {ip} to VM {name}.")
    else:
        console.print(f"[bold red]Failed to assign floating IP to VM {name}.[/bold red]", stderr=True)

@vm_group.command()
@click.argument("name")
@click.pass_context
def release_floating_ip(ctx, name):
    """Release the floating IP of the VM"""
    provider = get_active_provider(ctx)
    if not hasattr(provider, "release_floating_ip"):
        console.print(f"[bold red]Error: Provider '{provider.cloud_name}' does not support floating IP release.[/bold red]", stderr=True)
        return

    if provider.release_floating_ip(name):
        console.print(f"Successfully released floating IP for VM {name}.")
    else:
        console.print(f"[bold red]Failed to release floating IP for VM {name}.[/bold red]", stderr=True)

@vm_group.group(name="key")
def key_group():
    """Manage SSH keys for the cloud provider"""
    pass

@key_group.command()
@click.argument("key_path", type=click.Path(exists=True))
@click.argument("key_name")
@click.pass_context
def upload(ctx, key_path, key_name):
    """Upload a public key to the cloud"""
    provider = get_active_provider(ctx)
    if not hasattr(provider, "upload_key"):
        console.print(f"[bold red]Error: Provider '{provider.cloud_name}' does not support key upload.[/bold red]", stderr=True)
        return

    if provider.upload_key(key_path, key_name):
        console.print(f"Successfully uploaded key {key_name} from {key_path}.")
    else:
        console.print(f"[bold red]Failed to upload key {key_name}.[/bold red]", stderr=True)

@key_group.command()
@click.argument("key_name")
@click.pass_context
def delete(ctx, key_name):
    """Delete a public key from the cloud"""
    provider = get_active_provider(ctx)
    if not hasattr(provider, "delete_key"):
        console.print(f"[bold red]Error: Provider '{provider.cloud_name}' does not support key deletion.[/bold red]", stderr=True)
        return

    if provider.delete_key(key_name):
        console.print(f"Successfully deleted key {key_name}.")
    else:
        console.print(f"[bold red]Failed to delete key {key_name}.[/bold red]", stderr=True)

entry_point = vm_group

def register(cli):
    """Registers the vm command group to the main CLI."""
    cli.add_command(vm_group, name="vm")
