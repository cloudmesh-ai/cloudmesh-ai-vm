import click
from .._shared.context import console, get_active_provider
from .._shared.exceptions import handle_errors
from .._shared.ui import render_table

@click.command()
@handle_errors
def list_keys(ctx: click.Context):
    """List all SSH keys for the current provider."""
    provider = get_active_provider(ctx)
    keys = provider.list_keys()
    if keys:
        render_table("SSH Keys", ["Name", "Fingerprint"], [[k.name, k.fingerprint] for k in keys])
    else:
        console.print("No SSH keys found.")

cmd = list_keys
