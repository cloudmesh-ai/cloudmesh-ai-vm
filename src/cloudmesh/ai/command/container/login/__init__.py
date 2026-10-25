import click
from cloudmesh.ai.command._shared.context import console

@click.command()
@click.argument("name")
@click.pass_context
def login_container(ctx: click.Context, name: str):
    """Log into a running Docker container."""
    manager = ctx.obj
    if manager.login(name):
        console.print(f"[green]Successfully logged into {name}[/green]")
    else:
        console.print(f"[red]Failed to log into {name}[/red]")
