import click
import yaml
import os
from typing import Any, Dict, Optional

# Mapping of cloud names to their provider classes
PROVIDERS = {
    "multipass": "src.local.MultipassManager.Provider",
    "wsl2": "src.local.Wsl2Manager.Provider",
    "vbox": "src.local.VBoxManager.Provider",
    "jetstream": "src.openstack.JetstreamManager.Provider",
    "chameleon": "src.openstack.ChameleonManager.Provider",
    "aws": "src.aws.AwsManager.Provider",
    "azure": "src.azure.AzureManager.Provider",
    "google": "src.google.GoogleManager.Provider",
}

CONFIG_PATH = os.path.expanduser("~/.config/cloudmesh/clouds.yaml")

def load_config() -> Dict[str, Any]:
    if not os.path.exists(CONFIG_PATH):
        return {"username": "user", "counter": 0, "clouds": {}, "default_cloud": "multipass"}
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f) or {}

def save_config(config: Dict[str, Any]):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(config, f)

def get_provider(config: Dict[str, Any], cloud_name: Optional[str] = None):
    if not cloud_name:
        cloud_name = config.get("default_cloud", "multipass")
    
    if cloud_name not in PROVIDERS:
        raise click.ClickException(f"Unsupported cloud provider: {cloud_name}")
    
    # Dynamic import of the provider class
    module_path, class_name = PROVIDERS[cloud_name].rsplit(".", 1)
    module = __import__(module_path, fromlist=[class_name])
    provider_class = getattr(module, class_name)
    
    return provider_class(config)


@vm.command(name="set")
@click.argument("cloud")
def set_cloud(cloud):
    """Set the default cloud provider"""
    config = load_config()
    config["default_cloud"] = cloud
    save_config(config)
    click.echo(f"Default cloud set to: {cloud}")

@vm.command()
@click.option("--name", help="Name of the VM")
def start(name):
    """Starts a VM"""
    config = load_config()
    provider = get_provider(config)
    
    vm_name = name
    if not vm_name:
        username = config.get("username", "user")
        counter = config.get("counter", 0) + 1
        vm_name = f"{username}{counter}"
        config["counter"] = counter
        save_config(config)
    
    try:
        result_name = provider.start(name=vm_name)
        click.echo(f"VM {result_name} started successfully.")
    except Exception as e:
        click.echo(f"Error starting VM: {e}", err=True)

@vm.command()
@click.option("--name", help="Name of the VM")
def stop(name):
    """Stops a VM"""
    config = load_config()
    provider = get_provider(config)
    
    if not name:
        click.echo("Error: Please provide the --name of the VM to stop.", err=True)
        return

    if provider.stop(name=name):
        click.echo(f"VM {name} stopped.")
    else:
        click.echo(f"Failed to stop VM {name}.", err=True)

@vm.command()
@click.option("--name", help="Name of the VM")
def delete(name):
    """Deletes a VM"""
    config = load_config()
    provider = get_provider(config)
    if not name:
        click.echo("Error: Please provide the --name of the VM to delete.", err=True)
        return

    if provider.delete(name=name):
        click.echo(f"VM {name} deleted.")
    else:
        click.echo(f"Failed to delete VM {name}.", err=True)

@click.group()
def cmc():
    """Cloudmesh AI VM Management Tool"""
    pass

@cmc.group()
def vm():
    """VM management commands"""
    pass

@vm.command()
@click.option("--json", "format_json", is_flag=True, help="Output in JSON")
@click.option("--yaml", "format_yaml", is_flag=True, help="Output in YAML")
@click.option("--csv", "format_csv", is_flag=True, help="Output in CSV")
@click.option("--table", "format_table", is_flag=True, default=True, help="Output in Table")
def list_vms(format_json, format_yaml, format_csv, format_table):
    """Lists VMs"""
    config = load_config()
    provider = get_provider(config)
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
        if vms:
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

@vm.command()
@click.option("--name", help="Name of the VM")
def login(name):
    """Logs into a VM"""
    config = load_config()
    provider = get_provider(config)
    if not name:
        click.echo("Error: Please provide the --name of the VM to login.", err=True)
        return

    if provider.login(name=name):
        click.echo(f"Logged into {name}.")
    else:
        click.echo(f"Failed to login to {name}.", err=True)

@vm.command()
@click.option("--name", help="Name of the VM")
def suspend(name):
    """Suspends a VM"""
    config = load_config()
    provider = get_provider(config)
    if not name:
        click.echo("Error: Please provide the --name of the VM to suspend.", err=True)
        return

    if provider.suspend(name=name):
        click.echo(f"VM {name} suspended.")
    else:
        click.echo(f"Failed to suspend VM {name}.", err=True)

@vm.command()
@click.option("--name", help="Name of the VM")
def restart(name):
    """Restarts a VM"""
    config = load_config()
    provider = get_provider(config)
    if not name:
        click.echo("Error: Please provide the --name of the VM to restart.", err=True)
        return

    if provider.restart(name=name):
        click.echo(f"VM {name} restarted.")
    else:
        click.echo(f"Failed to restart VM {name}.", err=True)

@vm.command()
@click.option("--name", required=True, help="Name of the reservation")
@click.option("--node-type", required=True, help="Type of node (e.g. compute_skylake)")
@click.option("--count", type=int, required=True, help="Number of nodes")
@click.option("--start", help="Start date (YYYY-MM-DD HH:MM)")
@click.option("--end", help="End date (YYYY-MM-DD HH:MM)")
@click.option("--duration", type=int, help="Duration of the lease in days")
def reservation(name, node_type, count, start, end, duration):
    """Creates a reservation in Chameleon Cloud"""
    config = load_config()
    
    cloud_name = config.get("default_cloud", "multipass")
    if cloud_name != "chameleon":
        click.echo(f"Error: 'reservation' is only supported for the 'chameleon' cloud. Current cloud is '{cloud_name}'.", err=True)
        return

    provider = get_provider(config)
    
    if not hasattr(provider, "create_reservation"):
        click.echo("Error: Current provider does not support reservations.", err=True)
        return

    if provider.create_reservation(name=name, node_type=node_type, count=count, start_date=start, end_date=end, duration=duration):
        click.echo(f"Reservation {name} created successfully.")
    else:
        click.echo(f"Failed to create reservation {name}.", err=True)

if __name__ == "__main__":
    cmc()

