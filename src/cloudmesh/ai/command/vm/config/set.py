import click
from .._shared.context import console, state
from .._shared.exceptions import handle_errors

@click.command()
@click.argument("key")
@click.argument("value")
@handle_errors
def set_config(ctx: click.Context, key: str, value: str):
    """Set a configuration value."""
    state.config.set(key, value)
    console.print(f"Configured [bold green]{key}[/bold green] = {value}.")

cmd = set_config
