import click
from .context import console, get_active_provider, vm_options

@click.command()
@click.argument("name")
@vm_options
def assign_floating_ip(ctx, name):
    """Assign an available floating IP to the VM"""
    provider = get_active_provider(ctx)
    if not hasattr(provider, "assign_floating_ip"):
        console.print(f"[bold red]Error: Provider '{provider.cloud_name}' does not support floating IP assignment.[/bold red]")
        return

    ip = provider.assign_floating_ip(name)
    if ip:
        console.print(f"Successfully assigned floating IP {ip} to VM {name}.")
    else:
        console.print(f"[bold red]Failed to assign floating IP to VM {name}.[/bold red]")

@click.command()
@click.argument("name")
@vm_options
def release_floating_ip(ctx, name):
    """Release the floating IP of the VM"""
    provider = get_active_provider(ctx)
    if not hasattr(provider, "release_floating_ip"):
        console.print(f"[bold red]Error: Provider '{provider.cloud_name}' does not support floating IP release.[/bold red]")
        return

    if provider.release_floating_ip(name):
        console.print(f"Successfully released floating IP for VM {name}.")
    else:
        console.print(f"[bold red]Failed to release floating IP for VM {name}.[/bold red]")
