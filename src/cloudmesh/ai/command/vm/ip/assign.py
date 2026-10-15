import click
from .._shared.context import console, get_active_provider
from .._shared.exceptions import handle_errors, VMCommandError

@click.command()
@click.pass_context
@click.argument("name")
@handle_errors
def assign_ip(ctx: click.Context, name: str):
    """Assign a floating IP to a VM."""
    provider = get_active_provider(ctx)
    ip = provider.assign_floating_ip(name)
    if ip:
        console.print(f"Assigned floating IP [bold green]{ip}[/bold green] to VM {name}.")
    else:
        raise VMCommandError(f"Failed to assign a floating IP to VM {name}.")

cmd = assign_ip
