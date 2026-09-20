import click
from .context import console, get_active_provider, vm_options

@click.command()
@click.argument("name")
@vm_options
def info(ctx, name):
    """Gets detailed information about a VM"""
    provider = get_active_provider(ctx)
    vm_info = provider.info(name)
    
    if "error" in vm_info:
        console.print(f"[bold red]Error: {vm_info['error']}[/bold red]")
        return
    
    console.print(f"\nInformation for VM: {name}")
    console.print("-" * 30)
    for key, value in vm_info.items():
        console.print(f"{key:<15}: {value}")
    console.print("-" * 30)
