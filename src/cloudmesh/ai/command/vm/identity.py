import click
from rich.table import Table
import rich.box as box
from .context import console, get_active_provider, vm_options

@click.command()
@vm_options
def keys(ctx):
    """Lists available SSH keys"""
    provider = get_active_provider(ctx)
    keys_list = provider.get_keys()
    if not keys_list:
        console.print(f"No keys found or not supported by provider '{provider.cloud_name}'.")
        return
    
    # Use Rich table for a professional look
    table = Table(title=f"SSH Keys in {provider.cloud_name}", box=box.SQUARE, show_header=True, header_style="bold magenta")
    
    headers = keys_list[0].keys()
    for h in headers:
        table.add_column(h)
    
    for k in keys_list:
        table.add_row(*[str(v) for v in k.values()])
    
    console.print(table)

@click.command()
@vm_options
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

@click.command()
@vm_options
def ssh_config(ctx):
    """Suggests SSH config entries for existing VMs"""
    provider = get_active_provider(ctx)
    from cloudmesh.ai.vm.state_manager import state
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

@click.group(name="key")
def key_group():
    """Manage SSH keys for the cloud provider"""
    pass

@key_group.command(name="upload")
@click.argument("key_path", type=click.Path(exists=True))
@click.argument("key_name")
@vm_options
def key_upload(ctx, key_path, key_name):
    """Upload a public key to the cloud"""
    provider = get_active_provider(ctx)
    if not hasattr(provider, "upload_key"):
        console.print(f"[bold red]Error: Provider '{provider.cloud_name}' does not support key upload.[/bold red]")
        return

    if provider.upload_key(key_path, key_name):
        console.print(f"Successfully uploaded key {key_name} from {key_path}.")
    else:
        console.print(f"[bold red]Failed to upload key {key_name}.[/bold red]")

@key_group.command(name="delete")
@click.argument("key_name")
@vm_options
def key_delete(ctx, key_name):
    """Delete a public key from the cloud"""
    provider = get_active_provider(ctx)
    if not hasattr(provider, "delete_key"):
        console.print(f"[bold red]Error: Provider '{provider.cloud_name}' does not support key deletion.[/bold red]")
        return

    if provider.delete_key(key_name):
        console.print(f"Successfully deleted key {key_name}.")
    else:
        console.print(f"[bold red]Failed to delete key {key_name}.[/bold red]")
