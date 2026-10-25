import importlib
import logging
import os
from typing import Optional

import click


def load_commands_recursively(group: click.Group, current_dir: str, package_path: str):
    """
    Recursively scans the directory for .py files and folders,
    adding them as commands or subgroups to the provided group.
    """
    for entry in os.listdir(current_dir):
        # Ignore internal folders, files, and __init__.py
        if entry.startswith("_") or entry == "__init__.py":
            continue

        full_path = os.path.join(current_dir, entry)

        if os.path.isdir(full_path):
            # 1. Handle Sub-groups (folders)
            group_name = entry
            module_path = f"{package_path}.{group_name}"
            try:
                mod = importlib.import_module(module_path)
                group_obj = getattr(mod, "cmd", None)

                if not group_obj or not isinstance(group_obj, click.Group):
                    # Fallback: Create a generic group if 'cmd' is missing or not a Group
                    group_obj = click.Group(name=group_name)

                group.add_command(group_obj, name=group_name.replace("_", "-"))

                # Recurse into the folder
                load_commands_recursively(group_obj, full_path, module_path)

            except Exception as e:
                logging.error(
                    f"Failed to load group {group_name} from {module_path}: {e}"
                )

        elif entry.endswith(".py"):
            # 2. Handle Commands (files)
            cmd_name = entry[:-3]
            module_path = f"{package_path}.{cmd_name}"
            try:
                mod = importlib.import_module(module_path)
                cmd_obj = getattr(mod, "cmd", None)

                if cmd_obj:
                    group.add_command(cmd_obj, name=cmd_name.replace("_", "-"))
                else:
                    logging.warning(
                        f"Module {module_path} does not export a 'cmd' object."
                    )

            except Exception as e:
                logging.error(
                    f"Failed to load command {cmd_name} from {module_path}: {e}"
                )


@click.group()
def cmx() -> None:
    """Cloudmesh AI CLI"""


# We will import and add subgroups here to avoid circular imports
# during the initial group definition.
def init_cmx():
    from .key import key_group
    from .vm import vm_group
    from .container import container_group
    cmx.add_command(container_group, name="container")


    cmx.add_command(vm_group, name="vm")
    cmx.add_command(key_group, name="key")


# Initialize the commands
init_cmx()
