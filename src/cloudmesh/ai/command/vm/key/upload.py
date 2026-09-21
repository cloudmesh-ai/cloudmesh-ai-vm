import click
import os
from .._shared.context import console, get_active_provider
from .._shared.exceptions import handle_errors, VMCommandError

@click.command()
@click.pass_context
@click.argument("key_path", required=False)
@click.option("--name", help="Custom name for the key")
@handle_errors
def upload_key(ctx: click.Context, key_path: str = None, name: str = None):
    """Upload a public SSH key to the cloud provider."""
    if not key_path:
        key_path = os.path.expanduser("~/.ssh/id_rsa.pub")
    
    provider = get_active_provider(ctx)
    if provider.upload_key(key_path, name):
        console.print(f"Successfully uploaded key [bold green]{key_path}[/bold green].")
    else:
        raise VMCommandError(f"Failed to upload key {key_path}.")

cmd = upload_key
