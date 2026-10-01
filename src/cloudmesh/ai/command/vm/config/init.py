import click
import getpass
from .._shared.context import console, state
from .._shared.exceptions import handle_errors

@click.command()
@click.pass_context
@handle_errors
def init_config(ctx: click.Context):
    """Initialize the VM CLI configuration."""
    defaults = {
        "default_cloud": "multipass",
        "username": getpass.getuser().replace("_", "-"),
        "counter": 0,
        "clouds.multipass": {
            "enabled": True, "image": "24.04", "cpus": 2,
            "memory": "2G", "disk": "10G",
        },
    }
    for key, value in defaults.items():
        if state.db.get(key) is None:
            state.db.set(key, value)
    console.print("VM configuration initialized.")

cmd = init_config
