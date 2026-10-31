import click

from cloudmesh.ai.command.key.delete import delete_key
from cloudmesh.ai.command.key.list import list_keys
from cloudmesh.ai.command.vm.key.upload import upload_key


@click.group(name="key")
def key_group():
    """SSH key management commands for the current VM provider."""


# Add the existing logic from the 'cmx key' namespace
key_group.add_command(list_keys, name="list")
key_group.add_command(upload_key, name="upload")
key_group.add_command(delete_key, name="delete")

cmd = key_group
