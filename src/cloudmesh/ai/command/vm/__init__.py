import importlib
import logging
import os
import shlex
from typing import Optional

import click

from cloudmesh.ai.command._shared.context import (
    VMContext,
    cloud_callback,
    console,
    debug_callback,
    verbose_callback,
)
from cloudmesh.ai.command._shared.providers_utils import register_providers
# Re-export the top‑level CLI entry point so that tests can import ``cmx``
# directly from ``cloudmesh.ai.command.vm``.
from cloudmesh.ai.command import cmx  # noqa: F401

# Register providers immediately so they are available to all commands
register_providers()

from cloudmesh.ai.command._shared.utils import load_commands_recursively


@click.group()
@click.option(
    "--cloud",
    callback=cloud_callback,
    expose_value=False,
    help="Override the default cloud provider",
)
@click.option(
    "--debug",
    is_flag=True,
    callback=debug_callback,
    expose_value=False,
    help="Enable debug logging",
)
@click.option(
    "--verbose",
    is_flag=True,
    callback=verbose_callback,
    expose_value=False,
    help="Print raw subprocess/SSH commands",
)
@click.option("-i", "--interactive", is_flag=True, help="Enter interactive mode")
@click.pass_context
def vm_group(ctx: click.Context, interactive: bool = False) -> None:
    """VM management commands"""
    ctx.ensure_object(VMContext)

    os_cloud = os.environ.get("OS_CLOUD")
    active_cloud = ctx.obj.cloud_override or os_cloud

    # We only enforce OS_CLOUD for commands that actually need a target cloud.
    # Commands like 'provider list' should be allowed without it.
    # Since we are in the group callback, we'll check if the command being called requires it.
    # For now, we'll allow it to be None and let the specific command handle the error if needed.
    if active_cloud:
        console.print(f"Running on cloud: [bold blue]{active_cloud}[/bold blue]")

    if interactive:
        console.print(
            "[bold green]Entering interactive VM shell. Type 'exit' or 'quit' to leave.[/bold green]"
        )

        while True:
            try:
                prompt = f"[bold blue]({active_cloud}) vm>[bold blue] "

                user_input = console.input(prompt)
                if not user_input.strip():
                    continue
                if user_input.strip().lower() in ("exit", "quit"):
                    break

                args = shlex.split(user_input)
                cmd_name = args[0]
                cmd_args = args[1:]

                # Use the group's get_command to find the command
                cmd = vm_group.get_command(ctx, cmd_name)
                if cmd:
                    ctx.invoke(cmd, *cmd_args)
                else:
                    console.print(
                        f"[red]Unknown command: {cmd_name}[/red]. Type 'help' for available commands."
                    )
            except KeyboardInterrupt:
                console.print("\\n[yellow]Use 'exit' to leave the shell.[/yellow]")
            except Exception as e:
                console.print(f"[bold red]Shell Error:[/bold red] {e!s}")
    else:
        pass


# Initialize the dynamic loading
COMMANDS_DIR = os.path.dirname(__file__)
load_commands_recursively(vm_group, COMMANDS_DIR, "cloudmesh.ai.command.vm")
