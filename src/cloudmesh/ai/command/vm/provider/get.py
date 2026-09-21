import click
from .._shared.context import console, state
from .._shared.exceptions import handle_errors

@click.command(name="get")
@click.pass_context
@handle_errors
def get_provider(ctx: click.Context):
    """Get the current default cloud provider."""
    provider = state.config.db.get("default_cloud", "multipass") or "multipass"
    console.print(f"Current provider: [bold green]{provider}[/bold green].")

cmd = get_provider
