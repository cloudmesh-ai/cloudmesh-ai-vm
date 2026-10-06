import click
import logging
import os
import re
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from cloudmesh.ai.vm.state_manager import StateManager

@dataclass
class VMContext:
    cloud_override: Optional[str] = None
    interactive: bool = False

# Initialize StateManager with the default config path or environment override
DEFAULT_CONFIG_PATH = os.path.expanduser("~/.config/cloudmesh/clouds.yaml")
CONFIG_PATH = os.environ.get("CLOUDMESH_VM_CONFIG", DEFAULT_CONFIG_PATH)
state_manager = StateManager(CONFIG_PATH)

class StateProxy:
    """
    Proxy class to provide easy access to the StateManager.
    """
    @property
    def config(self):
        return self._manager.config

    def save(self):
        """Saves the current configuration to the file."""
        # YamlDB usually auto-flush, but we keep this for API compatibility.
        pass

    def increment_counter(self) -> int:
        return self._manager.increment_counter()

    def set_last_vm(self, cloud_name: str, vm_name: str):
        self._manager.set_last_vm(cloud_name, vm_name)

    def get_last_vm(self, cloud_name: str) -> Optional[str]:
        return self._manager.get_last_vm(cloud_name)
    @property
    def db(self):
        return self._manager.db

    def set_manager(self, manager: StateManager):
        """Allows tests to inject a different StateManager."""
        self._manager = manager

# Create the singleton instance
state = StateProxy()
state.set_manager(state_manager)

def cloud_callback(ctx: click.Context, param, value):
    if value:
        if ctx.obj is None:
            ctx.obj = VMContext()
        ctx.obj.cloud_override = value
    return value

def debug_callback(ctx: click.Context, param, value):
    if value:
        logging.getLogger("cloudmesh.ai.vm").setLevel(logging.DEBUG)
    return value

def verbose_callback(ctx: click.Context, param, value):
    if value:
        pass
    return value

def get_active_provider(ctx: click.Context):
    from .providers_utils import register_providers
    register_providers()

    default_cloud = "multipass"
    if state.config:
        # Use StateManager.db.get for the default_cloud value
        default_cloud = state.config.db.get("default_cloud", "multipass") or "multipass"

    cloud = ctx.obj.cloud_override if ctx.obj else None
    if not cloud:
        cloud = default_cloud

    try:
        from cloudmesh.ai.vm.providers import get_provider
        return get_provider(cloud)
    except Exception as e:
        raise click.ClickException(f"Unsupported or misconfigured cloud provider: {cloud}. Error: {e}")

def resolve_vm_name(ctx: click.Context, name: Optional[str]) -> str:
    if name:
        return name

    provider = get_active_provider(ctx)
    cloud_name = provider.cloud_name
    last_vm = state.get_last_vm(cloud_name)

    if last_vm:
        return last_vm

    raise click.ClickException("No VM name provided and no recent VM found in session. Please provide a name.")

def vm_options(f):
    """Decorator to add common VM options."""
    return f

from rich.console import Console
console = Console()

def _parse_range(range_str: str) -> List[int]:
    """Parse a range string like '1-5' or '1' into a list of integers."""
    try:
        if '-' in range_str:
            start_str, end_str = range_str.split('-', 1)
            return list(range(int(start_str), int(end_str) + 1))
        return [int(range_str)]
    except ValueError as e:
        # We use click.ClickException here to avoid circular dependency with exceptions.py
        raise click.ClickException(f"Invalid range format '{range_str}'. Expected 'start-end' (e.g. 1-5).") from e

def _expand_hostlist(name: str, username: str) -> List[str]:
    """
    Expands a hostlist pattern like 'node[1-3]' into ['node-1', 'node-2', 'node-3'].
    """
    if '[' in name and name.endswith(']'):
        base, range_part = name.split('[', 1)
        range_str = range_part[:-1]
        indices = _parse_range(range_str)
        # Use a hyphen separator consistent with the username-counter pattern
        sep = "-" if base and not base.endswith("-") else ""
        return [f"{base}{sep}{i}" for i in indices]
    return [name]

def _filter_by_regex(pattern: str, provider) -> List[str]:
    """
    Filters VMs in the provider based on a regex or wildcard pattern.
    """
    # Convert glob wildcards to regex
    # * -> .*
    # ? -> .
    regex_pattern = pattern.replace('*', '.*').replace('?', '.')
    # Ensure we match from the start
    if not regex_pattern.startswith('^'):
        regex_pattern = '^' + regex_pattern

    try:
        compiled = re.compile(regex_pattern)
    except re.error as e:
        raise click.ClickException(f"Invalid regex pattern '{pattern}': {e}")

    all_vms = provider.list()
    matches = [vm["name"] for vm in all_vms if compiled.match(vm["name"])]
    return matches

def resolve_vms(ctx: click.Context, name: Optional[str] = None, count: Optional[int] = None, vm_range: Optional[str] = None) -> List[str]:
    """
    Resolves a list of VM names based on a name (single, hostlist, or regex), a count, or a range.
    """
    provider = get_active_provider(ctx)

    # 1. Determine the base username for range-based resolution
    provider_config = provider.get_cloud_config(provider.cloud_name)
    raw_username = provider_config.get("username") or state.config.db.get("username", "user")
    username = raw_username.replace("_", "-")

    vms: List[str] = []

    if vm_range:
        indices = _parse_range(vm_range)
        vms = [f"{username}-{i}" for i in indices]
        console.print(f"Targeting VMs in range {vm_range} ([bold blue]{', '.join(vms)}[/bold blue])")

    elif count:
        all_vms = provider.list()
        if not all_vms:
            raise click.ClickException("No VMs found.")

        timestamp_keys = ["created_at", "timestamp", "creation_time", "created"]
        sort_key = None
        for key in timestamp_keys:
            if all_vms and key in all_vms[0]:
                sort_key = key
                break

        if sort_key:
            all_vms.sort(key=lambda x: x.get(sort_key) or "", reverse=True)

        to_select = all_vms[:count]
        vms = [vm["name"] for vm in to_select]
        console.print(f"Targeting last {count} VMs: [bold blue]{', '.join(vms)}[/bold blue]")

    elif name:
        # 1. Explicit Wildcards/Anchors -> Definitely Regex
        if any(char in name for char in ['*', '?', '^', '$']):
            vms = _filter_by_regex(name, provider)
            if not vms:
                raise click.ClickException(f"No VMs found matching pattern: {name}")
            console.print(f"Pattern match. Targeting VMs: [bold blue]{', '.join(vms)}[/bold blue]")

        # 2. Hostlist Range (e.g., 'node[1-3]') or Regex with brackets
        elif '[' in name and name.endswith(']'):
            try:
                vms = _expand_hostlist(name, username)
                # If it expanded to multiple VMs, it was a valid range
                if len(vms) > 1:
                    console.print(f"Expanded hostlist. Targeting VMs: [bold blue]{', '.join(vms)}[/bold blue]")
                elif len(vms) == 1 and vms[0] == name:
                    # It didn't expand (returned [name]), so it's either a single VM
                    # or a regex that didn't match the range format.
                    # Try regex as a fallback.
                    vms = _filter_by_regex(name, provider)
                    if not vms:
                        vms = [name]
                    elif len(vms) > 1:
                        console.print(f"Pattern match. Targeting VMs: [bold blue]{', '.join(vms)}[/bold blue]")
                else:
                    # Expanded to 1 VM (e.g. node[1-1]), which is valid.
                    pass
            except click.ClickException:
                # Not a valid range, treat as regex
                vms = _filter_by_regex(name, provider)
                if not vms:
                    raise click.ClickException(f"No VMs found matching pattern: {name}")
                console.print(f"Pattern match. Targeting VMs: [bold blue]{', '.join(vms)}[/bold blue]")

        # 3. Other regex characters
        elif any(char in name for char in ['(', ')', '[', ']']):
            vms = _filter_by_regex(name, provider)
            if not vms:
                raise click.ClickException(f"No VMs found matching pattern: {name}")
            console.print(f"Pattern match. Targeting VMs: [bold blue]{', '.join(vms)}[/bold blue]")

        # 4. Exact match
        else:
            vms = [name]

    else:
        vm_name = resolve_vm_name(ctx, name)
        vms = [vm_name]

    return vms
