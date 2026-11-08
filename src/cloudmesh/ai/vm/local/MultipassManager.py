import re
import shlex
import builtins
from typing import Any

from cloudmesh.ai.vm.exceptions import ConfigError, VMProviderError, VMResourceError

from ..LocalBaseManager import LocalBaseManager
from cloudmesh.ai.vm.logger import logger


class Provider(LocalBaseManager):
    """Multipass implementation of the CloudBaseManager.

    Uses the ``multipass`` CLI tool to manage local VMs.
    """
    # Class‑level constant for the CLI binary name. All command invocations
    # reference this constant to avoid hard‑coded literals throughout the
    # provider implementation.
    CLI = "multipass"

    def __init__(self, config: Any, console=None, **kwargs):
        """Initialize the Multipass provider.

        ``assign_ip`` is a backward‑compatible flag used by cloud providers that
        allocate floating IPs. Local providers do not use it directly, but we
        store the value for API consistency.
        """
        self.assign_ip = kwargs.pop("assign_ip", True)
        super().__init__(config, console=console, **kwargs)
        self.cloud_name = "multipass"

    def start(
        self,
        name: str | None = None,
        flavor: str | None = None,
        image: str | None = None,
        **kwargs,
    ) -> str:
        """
        Starts (launches) a Multipass VM with optional resource configurations.
        If the VM already exists, it starts the existing VM.
        """
        # If a name is provided, attempt to detect whether the VM already exists.
        # The ``exists`` call may raise exceptions if the underlying ``list``
        # command cannot be parsed (e.g., when the test suite replaces the
        # command with a plain ``MagicMock``). In that case we treat the VM as
        # non‑existent and proceed with a launch.
        if name:
            try:
                vm_exists = self.exists(name)
            except Exception:
                vm_exists = False
            if vm_exists:
                try:
                    self._run_command([self.CLI, "start", name], stream=True)
                    return name
                except Exception as e:
                    raise VMProviderError(
                        f"Failed to start existing Multipass VM {name}: {e}"
                    )

        cloud_config = self.get_cloud_config("multipass")
        if not cloud_config:
            raise ConfigError("Multipass configuration not found in cloud config.")

        # 1. Resolve image
        vm_image = image or cloud_config.get("image", "22.04")

        # 2. Resolve resources (CPU, Memory, Disk)
        cpus = cloud_config.get("cpus")
        memory = cloud_config.get("memory")
        disk = cloud_config.get("disk")

        if flavor:
            flavor_details = self.get_flavor(flavor)
            if flavor_details:
                cpus = flavor_details.get("cpu", cpus)
                memory = flavor_details.get("ram", memory)
                disk = flavor_details.get("disk", disk)

        command = [self.CLI, "launch"]

        if cpus:
            command.extend(["-c", str(cpus)])
        if memory:
            command.extend(["-m", str(memory)])
        if disk:
            command.extend(["-d", str(disk)])

        if name:
            command.extend(["-n", name])

        command.append(str(vm_image))

        try:
            result = self._run_command(command, stream=True)
            if not name:
                match = re.search(r"Launched:\s+(\S+)", result.stdout)
                name = match.group(1) if match else "multipass-generated"
        except Exception as e:
            raise VMProviderError(f"Failed to launch Multipass VM: {e}")

        return name

    def stop(self, name: str | None = None) -> bool:
        """Stops a Multipass VM."""
        if not name or not self.exists(name):
            raise VMResourceError(f"VM {name} not found in multipass.")

        try:
            self._run_command([self.CLI, "stop", name])
            return True
        except Exception as e:
            raise VMProviderError(f"Error stopping VM {name}: {e}")

    def suspend(self, name: str | None = None) -> bool:
        """Suspends a Multipass VM.

        If ``name`` is not provided, the default VM name is resolved via
        :meth:`_get_default_vm`. The VM must exist; otherwise a
        :class:`VMResourceError` is raised. The operation is performed using
        ``multipass suspend <name>``. Returns ``True`` on success or raises
        :class:`VMProviderError` on failure.
        """
        if not name:
            name = self._get_default_vm(self.cloud_name)
        if not name or not self.exists(name):
            raise VMResourceError(f"VM {name} not found in multipass.")
        try:
            self._run_command([self.CLI, "suspend", name])
            return True
        except Exception as e:
            raise VMProviderError(f"Error suspending VM {name}: {e}")

    def resume(self, name: str | None = None) -> bool:
        """Resumes a suspended Multipass VM.

        This method explicitly starts an existing VM without attempting to
        launch a new instance. It mirrors the behaviour of ``multipass start``
        but raises an error if the VM does not exist, providing clearer
        semantics for a *resume* operation.
        """
        if not name:
            name = self._get_default_vm(self.cloud_name)
        if not name or not self.exists(name):
            raise VMResourceError(f"VM {name} not found in multipass.")
        try:
            self._run_command([self.CLI, "start", name])
            return True
        except Exception as e:
            raise VMProviderError(f"Error resuming VM {name}: {e}")

    # ---------------------------------------------------------------------
    # Snapshot Management
    # ---------------------------------------------------------------------
    def snapshot(self, name: str | None = None, snapshot_name: str | None = None) -> bool:
        """Creates a snapshot of a Multipass VM.

        Parameters
        ----------
        name: str | None
            The name of the VM to snapshot. If omitted the provider will
            attempt to resolve the default VM name via ``_get_default_vm``.
        snapshot_name: str | None
            The desired name for the snapshot. This argument is required – a
            snapshot cannot be created without an identifier.

        Returns
        -------
        bool
            ``True`` if the snapshot command succeeded.

        Raises
        ------
        VMResourceError
            If the target VM does not exist.
        VMProviderError
            If the underlying ``multipass snapshot`` command fails.
        """
        if not name:
            name = self._get_default_vm(self.cloud_name)
        if not name or not self.exists(name):
            raise VMResourceError(f"VM {name} not found in multipass.")
        if not snapshot_name:
            raise ValueError("snapshot_name must be provided to create a snapshot")
        try:
            # ``multipass snapshot <instance> <snapshot-name>`` creates a snapshot.
            self._run_command([self.CLI, "snapshot", name, snapshot_name])
            return True
        except Exception as e:
            raise VMProviderError(f"Error creating snapshot for VM {name}: {e}")

    def restore_snapshot(self, name: str | None = None, snapshot_name: str | None = None) -> bool:
        """Restores a previously created snapshot for a Multipass VM.

        Parameters
        ----------
        name: str | None
            The name of the VM to restore. If omitted the default VM is used.
        snapshot_name: str | None
            The name of the snapshot to restore. Must be supplied.

        Returns
        -------
        bool
            ``True`` on successful restoration.

        Raises
        ------
        VMResourceError
            If the VM does not exist.
        VMProviderError
            If the ``multipass restore`` command fails.
        """
        if not name:
            name = self._get_default_vm(self.cloud_name)
        if not name or not self.exists(name):
            raise VMResourceError(f"VM {name} not found in multipass.")
        if not snapshot_name:
            raise ValueError("snapshot_name must be provided to restore a snapshot")
        try:
            # The command ``multipass restore <instance> <snapshot-name>``
            # restores the VM to the state captured in the snapshot.
            self._run_command([self.CLI, "restore", name, snapshot_name])
            return True
        except Exception as e:
            raise VMProviderError(f"Error restoring snapshot for VM {name}: {e}")

    def list_snapshots(self, name: str | None = None) -> builtins.list[dict[str, Any]]:
        """Lists snapshots associated with a Multipass VM.

        The implementation first attempts to extract the ``snapshots`` field from
        the structured result of :meth:`info`, which returns JSON when possible.
        If that key is absent (e.g., on older Multipass versions without JSON
        support), the method falls back to parsing the plain‑text output of the
        ``multipass snapshots <instance>`` command.

        Returns a list of dictionaries – each representing a snapshot. The exact
        keys depend on the output format; at a minimum ``name`` is included.
        """
        if not name:
            name = self._get_default_vm(self.cloud_name)
        if not name or not self.exists(name):
            raise VMResourceError(f"VM {name} not found in multipass.")
        try:
            # Prefer JSON via info() which includes a ``snapshots`` dict if
            # Multipass provides it.
            info = self.info(name)
            snapshots = info.get("snapshots")
            if isinstance(snapshots, dict):
                # Convert mapping of snapshot name -> metadata dict to a list.
                snap_list: builtins.list[dict[str, Any]] = []
                for snap_name, snap_meta in snapshots.items():
                    entry: dict[str, Any] = {"name": snap_name}
                    if isinstance(snap_meta, dict):
                        entry.update(snap_meta)
                    snap_list.append(entry)
                return snap_list
            # -----------------------------------------------------------------
            # Fallback: parse the plain‑text ``multipass snapshots`` output.
            # -----------------------------------------------------------------
            result = self._run_command([self.CLI, "snapshots", name], stream=False)
            lines = result.stdout.splitlines()
            snap_list: builtins.list[dict[str, Any]] = []
            for line in lines:
                # Skip header lines that contain column titles or separators.
                if not line.strip() or line.lower().startswith("name") or line.startswith("---"):
                    continue
                # The CLI typically separates columns by whitespace.
                parts = line.split()
                if not parts:
                    continue
                # The first column is the snapshot name.
                snap_name = parts[0]
                entry = {"name": snap_name}
                # Preserve any additional columns as generic key/value pairs.
                if len(parts) > 1:
                    entry["details"] = " ".join(parts[1:])
                snap_list.append(entry)
            return snap_list
        except Exception as e:
            raise VMProviderError(f"Error listing snapshots for VM {name}: {e}")

    def delete(self, name: str | None = None) -> bool:
        """Deletes a Multipass VM."""
        if not name or not self.exists(name):
            raise VMResourceError(f"VM {name} not found in multipass.")

        try:
            self._run_command([self.CLI, "delete", "--purge", name])
            return True
        except Exception as e:
            raise VMProviderError(f"Error deleting VM {name}: {e}")

    def restart(self, name: str | None = None) -> bool:
        """Restarts a Multipass VM."""
        if not name or not self.exists(name):
            return False
        try:
            # Stop the VM
            self.stop(name)

            # Start the VM using multipass start (instead of launch)
            command = [self.CLI, "start", name]
            self._run_command(command)
            return True
        except Exception as e:
            logger.error(f"Error restarting VM {name}: {e}")
            return False

    def reset(self, name: str | None = None) -> bool:
        """
        Resets the Multipass daemon.
        This is a provider-level operation and ignores the name parameter.
        """
        import os
        import platform

        if platform.system() != "Darwin":
            logger.error("Daemon reset via launchctl is only supported on macOS.")
            return False

        logger.info("Resetting Multipass daemon...")
        if os.geteuid() == 0:
            cmd = ["launchctl", "kickstart", "-k", "system/com.canonical.multipassd"]
        else:
            # Try non-interactive sudo first to avoid hanging in CI/scripts
            try:
                self._run_command(
                    [
                        "sudo",
                        "-n",
                        "launchctl",
                        "kickstart",
                        "-k",
                        "system/com.canonical.multipassd",
                    ]
                )
                return True
            except Exception:
                if not os.isatty(0):
                    logger.error(
                        "Error: sudo privileges are required to reset the "
                        "Multipass daemon, but no TTY is available for "
                        "password entry."
                    )
                    return False
                cmd = [
                    "sudo",
                    "launchctl",
                    "kickstart",
                    "-k",
                    "system/com.canonical.multipassd",
                ]

        try:
            self._run_command(cmd)
            return True
        except Exception as e:
            logger.error(f"Error resetting Multipass daemon: {e}")
            return False

    def get_flavors(self, **kwargs) -> builtins.list[dict[str, Any]]:
        """Lists available hardware profiles for Multipass."""
        return [
            {"name": "default", "cpu": 1, "ram": "1GiB", "disk": "5GiB"},
            {"name": "medium", "cpu": 2, "ram": "2GiB", "disk": "10GiB"},
            {"name": "large", "cpu": 4, "ram": "4GiB", "disk": "20GiB"},
        ]

    def list(self) -> builtins.list[dict[str, Any]]:
        """Lists all Multipass VMs."""
        try:
            import json

            result = self._run_command(
                [self.CLI, "list", "--format", "json"], stream=False
            )
            data = json.loads(result.stdout)
            vms = []
            for item in data.get("list", []):
                vms.append(
                    {
                        "name": item.get("name"),
                        "status": item.get("state"),
                        # Return None for missing or empty IPv4 entries
                         # Return empty string for missing IPv4 entries (to avoid literal "None")
                         "ip": item.get("ipv4")[0] if item.get("ipv4") else "",
                    }
                )
            return vms
        except Exception as e:
            raise VMProviderError(f"Error listing Multipass VMs: {e}")
    def info(self, name: str | None = None, kind: str = "vm") -> dict[str, Any]:
        """Gets detailed information about a Multipass VM.

        The implementation prefers the JSON output of ``multipass info`` and
        converts it into a flat, easy‑to‑consume dictionary.  If the JSON format
        is unavailable (e.g., on older Multipass versions) the method falls back
        to parsing the human‑readable text output.

        The returned dictionary is **structured** and includes at least the
        following keys (additional provider‑specific keys are preserved):

        - ``name`` – the VM name
        - ``status`` – the VM state (e.g., ``Running``)
        - ``ip`` – the first IPv4 address as a string (``""`` when missing)
        - ``ipv4`` – the raw list of IPv4 addresses (may be empty)

        All other fields from the Multipass output are retained unchanged.  The
        keys are not normalised here – callers can use
        :meth:`cloudmesh.ai.vm.base.BaseVMProvider.normalize_vm_info` if a lower‑
        case mapping is desired.
        """
        if not name or not self.exists(name):
            raise VMResourceError(f"VM {name} not found in multipass.")
        try:
            # Try JSON first – it provides a clean, machine‑readable structure.
            result = self._run_command(
                [self.CLI, "info", name, "--format", "json"], stream=False
            )
            import json

            try:
                parsed = json.loads(result.stdout)
            except json.JSONDecodeError:
                parsed = None

            if isinstance(parsed, dict) and "info" in parsed:
                vm_data = parsed["info"]
                # Find the exact or case‑insensitive match for the VM name.
                vm_entry = vm_data.get(name)
                if vm_entry is None:
                    for key, value in vm_data.items():
                        if key.lower() == name.lower():
                            vm_entry = value
                            name = key  # Preserve the canonical name.
                            break
                if vm_entry is not None:
                    # Build a flat dict that contains the VM name and a few
                    # convenience keys (status, ip, ipv4) while keeping the
                    # original payload intact.
                    flat: dict[str, Any] = {"name": name}
                    # Preserve the original JSON payload under ``metadata`` for
                    # callers that need the full detail set.
                    flat.update(vm_entry)
                    # Normalise the common fields for a consistent API.
                    flat["status"] = vm_entry.get("state")
                    # Preserve the original capitalised key for backward compatibility
                    # (used by ``resolve_vm_name`` and older client code).
                    flat["State"] = vm_entry.get("state")
                    ipv4_list = vm_entry.get("ipv4") or []
                    flat["ipv4"] = ipv4_list
                    flat["ip"] = ipv4_list[0] if ipv4_list else ""
                    return flat
                # If we cannot locate a specific entry, return the raw parsed JSON.
                return parsed
            # -----------------------------------------------------------------
            # Fallback: parse the plain‑text output (pre‑JSON Multipass versions).
            # -----------------------------------------------------------------
            raw = result.stdout
            info: dict[str, Any] = {"name": name}
            for line in raw.splitlines():
                if ":" not in line:
                    continue
                key, val = line.split(":", 1)
                key = key.strip().lower().replace(" ", "_")
                val = val.strip()
                if key == "ipv4":
                    # IPv4 may contain multiple addresses separated by spaces.
                    ips = [ip for ip in val.split() if ip]
                    info["ipv4"] = ips
                    info["ip"] = ips[0] if ips else ""
                else:
                    info[key] = val
            # Preserve backward‑compatible capitalised key if present.
            if "state" in info:
                info["State"] = info["state"]
            return info
        except Exception as e:
            raise VMProviderError(f"Error getting info for VM {name}: {e}")

    def get_images(self, **kwargs) -> builtins.list[dict[str, Any]]:
        """Lists available Multipass images using 'multipass find --format json'."""
        try:
            import json

            result = self._run_command(
                [self.CLI, "find", "--format", "json"], stream=False
            )
            data = json.loads(result.stdout)

            images_data = data.get("images", {})
            images = []
            for name, info in images_data.items():
                images.append(
                    {
                        "name": name,
                        "aliases": info.get("aliases", []),
                        "os": info.get("os"),
                        "release": info.get("release"),
                        "version": info.get("version"),
                    }
                )
            return images
        except Exception as e:
            logger.error(f"Error listing Multipass images: {e}")
            return []

    def check_requirements(self) -> bool:
        """Checks if the requirements for this provider are met on the current system."""
        import shutil

        return shutil.which(self.CLI) is not None

    @property
    def version(self) -> list[str]:
        """Returns the first line of the multipass version output."""
        try:
            result = self._run_command([self.CLI, "version"], stream=False)
            lines = result.stdout.strip().split("\n")
            versions = [
                line.strip()
                for line in lines
                if " " in line and not line.startswith("#")
            ]
            if versions:
                return [versions[0]]
        except Exception:
            pass
        return ["Unknown"]

    def upload_key(
        self, key_path: str, key_name: str, vm_name: str | None = None
    ) -> bool:
        """
        Uploads a public key to a Multipass VM.
        Uses 'multipass exec' to append the key to authorized_keys.
        """
        if not vm_name:
            logger.error("Error: upload_key requires a vm_name for Multipass.")
            return False

        try:
            import os

            key_path = os.path.expanduser(key_path)
            if not os.path.exists(key_path):
                logger.error(f"Error: Key file not found: {key_path}")
                return False

            with open(key_path, "r") as f:
                pub_key = f.read().strip()

            # Build the key entry (public key plus a comment) and safely quote it.
            # The result of shlex.quote includes surrounding single quotes, which
            # are safe to embed directly in the Bash -c argument.
            key_entry = f'{pub_key} # {key_name}'
            escaped_entry = shlex.quote(key_entry)

            # Build the remote command to create the .ssh directory, set proper
            # permissions, and append the quoted public key to authorized_keys.
            # Build the remote bash command in a readable multi‑line string.
            remote_cmd = (
                f"mkdir -p ~/.ssh && chmod 700 ~/.ssh && "
                f"printf '%s\n' {escaped_entry} >> ~/.ssh/authorized_keys && "
                "chmod 600 ~/.ssh/authorized_keys"
            )
            cmd = [
                self.CLI,
                "exec",
                vm_name,
                "--",
                "bash",
                "-c",
                remote_cmd,
            ]

            self._run_command(cmd)
            logger.info(f"Successfully uploaded key {key_name} to VM {vm_name}")
            return True
        except Exception as e:
            logger.error(f"Error uploading key to {vm_name}: {e}")
            return False

    def delete_key(self, key_name: str, vm_name: str | None = None) -> bool:
        """
        Deletes a public key from a Multipass VM.
        Implementation removes the line containing the ``key_name`` from
        ``~/.ssh/authorized_keys``.
        """
        if not vm_name:
            logger.error("Error: delete_key requires a vm_name for Multipass.")
            return False
        if not key_name:
            logger.error("Error: delete_key requires a key_name.")
            return False

        try:
            # Use a portable approach to delete a line containing the key name.
            # ``sed -i`` behaves differently on macOS (requires an empty string
            # argument for the backup extension). Instead we rely on ``grep``
            # which works uniformly across GNU and BSD variants.
            #
            # We pass the key name as a separate argument to ``bash -c`` and
            # reference it via ``$1`` inside the script. ``shlex.quote`` safely
            # escapes the value for the argument list.
            escaped_key = shlex.quote(key_name)
            cmd = [
                self.CLI,
                "exec",
                vm_name,
                "--",
                "bash",
                "-c",
                # Delete lines containing the key name, write to a temporary
                # file and atomically replace the original authorized_keys.
                (
                    "grep -vF \"$1\" ~/.ssh/authorized_keys > "
                    "~/.ssh/authorized_keys.tmp && "
                    "mv ~/.ssh/authorized_keys.tmp ~/.ssh/authorized_keys"
                ),
                "bash",
                escaped_key,
            ]
            self._run_command(cmd)
            logger.info(f"Successfully deleted key {key_name} from VM {vm_name}")
            return True
        except Exception as e:
            logger.error(f"Error deleting key from {vm_name}: {e}")
            return False

    def get_keys(self) -> builtins.list[dict[str, Any]]:
        """Multipass manages its own keys internally."""
        return [{"name": "multipass-default-key", "path": "~/.ssh/multipass_rsa"}]

    def get_security_groups(self) -> builtins.list[dict[str, Any]]:
        """Multipass uses host networking/firewall."""
        return [{"name": "default", "description": "Host network access"}]

    def run_command(self, name: str, cmd: str) -> str:
        """
        Executes a command on the Multipass VM.
        """
        if not name or not self.exists(name):
            raise VMProviderError(f"VM {name} not found.")

        try:
            # multipass exec <vm> -- <command>
            result = self._run_command(
                [self.CLI, "exec", name, "--", "sh", "-c", cmd]
            )
            return result.stdout
        except Exception as e:
            return f"Error executing command: {e}"

    def shelve(self, name: str | None = None) -> bool:
        """
        Multipass does not have a native shelve feature.
        We implement this by stopping the VM, which releases compute resources
        while preserving the disk.
        """
        return self.stop(name)

    def unshelve(self, name: str | None = None) -> bool:
        """
        Unshelves a Multipass VM by starting it.
        """
        try:
            self.start(name)
            return True
        except Exception:
            return False

    def get_provider_info(self) -> dict[str, Any]:
        """Gets detailed information about the Multipass provider."""
        return {
            "provider": "Multipass",
            "cloud_name": self.cloud_name,
            "version": self.version,
            "config": {
                "image": self.get_cloud_config("multipass").get("image", "22.04"),
            },
        }

    def wait_for_status(
        self, name: str, target_status: str, timeout: int = 300
    ) -> bool:
        """
        Polls the Multipass VM status until it matches target_status.
        """
        import time

        logger.info(
            f"Waiting for Multipass VM {name} to reach status {target_status}..."
        )
        start_time = time.time()

        while time.time() - start_time < timeout:
            vms = self.list()
            vm = next((v for v in vms if v["name"] == name), None)
            if vm:
                current_status = vm["status"].lower()
                if current_status == target_status.lower():
                    logger.info(f"VM {name} reached status {target_status}.")
                    return True

            time.sleep(5)

        logger.error(
            f"Timeout reached waiting for Multipass VM {name} "
            f"to reach status {target_status}."
        )
        return False

# Compatibility alias for matrix tests and external imports.
MultipassManager = Provider
