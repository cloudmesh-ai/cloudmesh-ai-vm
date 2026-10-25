import click

from cloudmesh.ai.command._shared.context import console


@click.command()
@click.argument("name")
@click.pass_context
def delete_container(ctx: click.Context, name: str):
    """Delete a Docker container."""
    manager = ctx.obj
    if manager.delete(name):
        console.print(f"[green]Container {name} deleted successfully.[/green]")
    else:
        console.print(f"[red]Failed to delete container {name}.[/red]")

