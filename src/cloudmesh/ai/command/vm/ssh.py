import os
import subprocess

import click

from cloudmesh.ai.command._shared.context import (
    console,
    get_active_provider,
    resolve_vm_name,
    vm_options,
)
from cloudmesh.ai.command._shared.exceptions import VMCommandError, handle_errors


@click.command()
@click.argument("name", required=False)
@vm_options
@handle_errors
@click.pass_context
def ssh(ctx: click.Context, name: str | None = None, **kwargs) -> None:
    """
    Start an interactive SSH session with the VM.
    If name is omitted, the last started VM is used.
    """
    provider = get_active_provider(ctx)
    vm_name = resolve_vm_name(ctx, name)

    if not vm_name:
        raise VMCommandError("No VM specified and no last-used VM found in context.")

    # Try to get VM info to find the IP
    info = provider.info(vm_name)
    if not info:
        raise VMCommandError(f"Could not find information for VM {vm_name}.")

    # Extract IP address (handles different provider formats)
    ip = None
    if isinstance(info, dict):
        ip = info.get("ip") or info.get("public_ip") or info.get("address")
        if isinstance(ip, list) and len(ip) > 0:
            ip = ip[0]
        elif isinstance(ip, dict):
            ip = ip.get("ip") or ip.get("address")

    if not ip:
        # Fallback: try to get floating IP if it's an OpenStack-like provider
        if hasattr(provider, "get_floating_ip"):
            ip = provider.get_floating_ip(vm_name)

    if not ip:
        raise VMCommandError(f"Could not resolve IP address for VM {vm_name}.")

    # Get SSH key path from config
    from cloudmesh.ai.command._shared.context import state

    cloud_config = state.config.get_cloud_config(provider.cloud_name) or {}
    key_path = cloud_config.get("key_path", "~/.ssh/id_rsa")
    user = cloud_config.get("user", "ubuntu")

    key_path = os.path.expanduser(key_path)

    # Build the SSH command
    # -t forces pseudo-terminal allocation which is needed for interactive shells
    ssh_cmd = [
        "ssh",
        "-i",
        key_path,
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=/dev/null",
        "-t",
        f"{user}@{ip}",
    ]

    console.print(f"[bold blue]Connecting to {vm_name} at {ip}...[/bold blue]")

    try:
        # Use subprocess.run without capture_output to allow interactive session
        result = subprocess.run(ssh_cmd)
        if result.returncode != 0:
            raise VMCommandError(
                f"SSH connection failed with exit code {result.returncode}."
            )
    except KeyboardInterrupt:
        pass
    except VMCommandError:
        raise
    except subprocess.CalledProcessError as e:
        raise VMCommandError(
            f"SSH connection failed with exit code {e.returncode}."
        ) from None
    except subprocess.TimeoutExpired:
        raise VMCommandError("SSH connection timed out.") from None
    except Exception:
        raise VMCommandError(
            "SSH connection failed due to an unexpected error."
        ) from None


cmd = ssh
