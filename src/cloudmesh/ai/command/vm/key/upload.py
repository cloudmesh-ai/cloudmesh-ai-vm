import click
from .._shared.context import console, get_active_provider
from .._shared.exceptions import handle_errors

@click.command()
@click.argument("key_path")
@click.option("--name", help="Custom name for the key")
@handle_errors
def upload_key(ctx: click.Context, key_path: str, name: str = None):
    """Upload a public SSH key to the cloud provider."""
    provider = get_active_provider(ctx)
    if provider.upload_key(key_path, name):
        console.print(f"Successfully uploaded key [bold green]{key_path}[/bold green].")
    else:
        raise VMCommandError(f"Failed to upload key {key_path}.")

cmd = upload_key
