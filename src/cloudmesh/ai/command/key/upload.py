import glob
import os

import click

from cloudmesh.ai.command._shared.context import console, get_active_provider
from cloudmesh.ai.command._shared.exceptions import VMCommandError, handle_errors


@click.command()
@click.pass_context
@click.argument("key_path", required=False)
@click.option("--name", help="Custom name for the key")
@handle_errors
def upload_key(ctx: click.Context, key_path: str = None, name: str = None):
    """Upload a public SSH key to the cloud provider."""
    provider = get_active_provider(ctx)
    config = provider.get_cloud_config(provider.cloud_name) or {}

    # Resolve key_path
    if not key_path:
        # 1. Try config
        key_path = config.get("key_path")

        if not key_path:
            # 2. Try default fallbacks in ~/.ssh/
            ssh_dir = os.path.expanduser("~/.ssh")
            fallbacks = ["id_ed25519.pub", "id_rsa.pub"]
            for fb in fallbacks:
                path = os.path.join(ssh_dir, fb)
                if os.path.exists(path):
                    key_path = path
                    break

            if not key_path:
                # 3. Try any *.pub file
                pub_files = glob.glob(os.path.join(ssh_dir, "*.pub"))
                if len(pub_files) == 1:
                    key_path = pub_files[0]
                elif len(pub_files) > 1:
                    raise VMCommandError(
                        f"Multiple public keys found in {ssh_dir} ({len(pub_files)} files). "
                        "The tool cannot decide which key to use. Please specify 'key_path' "
                        "as an argument or configure it in clouds.yaml."
                    )
                else:
                    raise VMCommandError(
                        f"No public keys found in {ssh_dir}. Please provide a key_path."
                    )

    key_path = os.path.expanduser(key_path)

    # Resolve name
    if not name:
        name = config.get("key_name")

    try:
        uploaded = provider.upload_key(key_path, name)
    except Exception:
        raise VMCommandError(
            "Failed to upload key due to a cloud provider error."
        ) from None

    if uploaded:
        console.print(f"Successfully uploaded key [bold green]{key_path}[/bold green].")
    else:
        raise VMCommandError(f"Failed to upload key {key_path}.")


cmd = upload_key
