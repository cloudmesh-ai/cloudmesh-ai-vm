import click
from .._shared.context import console, get_active_provider
from .._shared.exceptions import handle_errors

@click.command()
@click.pass_context
@click.argument("key_name")
@handle_errors
def delete_key(ctx: click.Context, key_name: str):
    """Delete an SSH key from the cloud provider."""
    provider = get_active_provider(ctx)
    if provider.delete_key(key_name):
        console.print(f"Successfully deleted key [bold green]{key_name}[/bold green].")
    else:
        raise VMCommandError(f"Failed to delete key {key_name}.")

cmd = delete_key
