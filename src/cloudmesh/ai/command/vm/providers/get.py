import click
from .._shared.context import console, state
from .._shared.exceptions import handle_errors

@click.command()
@handle_errors
def get_provider(ctx: click.Context):
    """Get the current default cloud provider."""
    provider = state.config.default_cloud or "multipass"
    console.print(f"Current provider: [bold green]{provider}[/bold green].")

cmd = get_provider
