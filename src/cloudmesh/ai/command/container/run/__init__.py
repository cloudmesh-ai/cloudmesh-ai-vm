import click
from cloudmesh.ai.command._shared.context import console

@click.command()
@click.option("--name", help="Name of the container")
@click.option("--image", default="ubuntu:latest", help="Docker image to use")
@click.pass_context
def run_container(ctx: click.Context, name: str | None, image: str):
    \"\"\"Run a Docker container.\"\"\"
    manager = ctx.obj
    result = manager.start(name=name, image=image)
    console.print(f\"[green]{result}[/green]\")

