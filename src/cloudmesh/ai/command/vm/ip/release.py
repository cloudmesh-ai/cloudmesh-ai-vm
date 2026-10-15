import click
from .._shared.context import console, get_active_provider
from .._shared.exceptions import handle_errors, VMCommandError

@click.command()
@click.pass_context
@click.argument("name")
@handle_errors
def release_ip(ctx: click.Context, name: str):
    """Release the floating IP of a VM."""
    provider = get_active_provider(ctx)
    if provider.release_floating_ip(name):
        console.print(f"Released the floating IP of VM [bold green]{name}[/bold green].")
    else:
        raise VMCommandError(f"Failed to release the floating IP of VM {name}.")

cmd = release_ip
