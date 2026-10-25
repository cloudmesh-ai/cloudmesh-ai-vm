import click

from cloudmesh.ai.command._shared.context import console


@click.command()
@click.argument("name")
@click.pass_context
def stop_container(ctx: click.Context, name: str):
    """Stop a Docker container."""
    manager = ctx.obj
    if manager.stop(name):
        console.print(f"[green]Container {name} stopped successfully.[/green]")
    else:
        console.print(f"[red]Failed to stop container {name}.[/red]")

