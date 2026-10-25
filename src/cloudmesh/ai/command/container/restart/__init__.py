import click
from cloudmesh.ai.command._shared.context import console

@click.command()
@click.argument("name")
@click.pass_context
def restart_container(ctx: click.Context, name: str):
    """Restart a Docker container."""
    manager = ctx.obj
    if manager.restart(name):
        console.print(f"[green]Container {name} restarted successfully.[/green]")
    else:
        console.print(f"[red]Failed to restart container {name}.[/red]")
