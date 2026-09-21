import click
from .._shared.context import console, state
from .._shared.exceptions import handle_errors

@click.command(name="set")
@click.pass_context
@click.argument("provider")
@handle_errors
def set_provider(ctx: click.Context, provider: str):
    """Set the default cloud provider."""
    state.db.set("default_cloud", provider)
    state.save()
    console.print(f"Default provider set to [bold green]{provider}[/bold green].")

cmd = set_provider
