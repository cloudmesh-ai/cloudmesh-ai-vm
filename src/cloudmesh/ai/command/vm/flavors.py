import click
from ._shared.context import console, get_active_provider, vm_options
from ._shared.exceptions import handle_errors
from ._shared.ui import render_table

@click.command()
@click.pass_context
@vm_options
@handle_errors
def flavors(ctx: click.Context):
    """List available VM flavors."""
    provider = get_active_provider(ctx)
    flv = provider.get_flavors() # Adjusted to use get_flavors()
    if flv:
        render_table("Flavors", ["Name", "CPU", "RAM"], [[f.get("name", "Unknown"), f.get("cpu", "Unknown"), f.get("ram", "Unknown")] for f in flv])
    else:
        console.print("No flavors found.")

cmd = flavors
