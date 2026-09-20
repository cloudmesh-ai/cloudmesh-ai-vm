import click
from ._shared.context import console, get_active_provider, vm_options
from ._shared.exceptions import handle_errors

@click.command()
@click.pass_context
@vm_options
@handle_errors
def ssh_config(ctx: click.Context):
    """Generate SSH config for the VM."""
    provider = get_active_provider(ctx)
    # Provider usually has a method to generate the config or we can format it
    config = provider.get_ssh_config() if hasattr(provider, "get_ssh_config") else None
    if config:
        console.print(config)
    else:
        console.print("Could not generate SSH config.")

cmd = ssh_config
