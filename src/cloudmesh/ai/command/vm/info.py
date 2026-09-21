import click
from typing import Optional
from ._shared.context import console, get_active_provider, vm_options, state
from ._shared.exceptions import handle_errors, VMCommandError

@click.command()
@click.pass_context
@click.argument("name")
@vm_options
@handle_errors
def info(ctx: click.Context, name: str) -> None:
    """
    Get detailed information about a specific VM.
    """
    provider = get_active_provider(ctx)
    
    # 1. Fetch VM information
    vm_info = provider.info(name)
    
    if not vm_info:
        raise VMCommandError(f"No information found for VM '{name}'.")
    
    if "error" in vm_info:
        raise VMCommandError(f"Could not retrieve info for VM '{name}': {vm_info['error']}")

    # 2. Display the information
    console.print(f"\n[bold blue]Information for VM: {name}[/bold blue]")
    console.print("-" * 30)
    
    # Iterate through the returned dictionary and print key-value pairs
    for key, value in vm_info.items():
        # Format keys to be more human-readable (e.g., "public_ip" -> "Public IP")
        display_key = key.replace("_", " ").title()
        console.print(f"[bold]{display_key}:[/bold] {value}")
    
    console.print("-" * 30)

cmd = info
