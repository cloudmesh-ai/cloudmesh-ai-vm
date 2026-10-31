"""Safety helpers for Chameleon smoke-test resources."""

import time

import chi


def verify_resources_absent(vm_name):
    """Refuse startup unless the exact VM and reservation names are unused."""
    if not vm_name or not isinstance(vm_name, str):
        raise ValueError("A non-empty VM name is required")

    reservation_name = f"res-{vm_name}"

    # Do not interpret API failures as an empty resource list.
    servers = chi.server.nova().servers.list(limit=-1)
    matching_servers = [
        server for server in servers
        if getattr(server, "name", None) == vm_name
    ]
    if matching_servers:
        raise RuntimeError(
            f"VM '{vm_name}' already exists; refusing smoke-test startup"
        )

    leases = chi.lease.list_leases()
    matching_leases = [
        lease for lease in leases
        if getattr(lease, "name", None) == reservation_name
    ]
    if matching_leases:
        raise RuntimeError(
            f"Reservation '{reservation_name}' already exists; "
            "refusing smoke-test startup"
        )


def cleanup_smoke_resources(vm_name):
    """Remove resources belonging to a preflight-verified smoke-test name.

    Call only after verify_resources_absent() succeeded before startup.
    """
    if not isinstance(vm_name, str) or not vm_name:
        raise ValueError("A non-empty VM name is required")

    reservation_name = f"res-{vm_name}"

    def matching_servers():
        servers = chi.server.nova().servers.list(limit=-1)
        return [
            server for server in servers
            if getattr(server, "name", None) == vm_name
        ]

    servers = matching_servers()
    if len(servers) > 1:
        raise RuntimeError(f"Multiple VMs named '{vm_name}'; refusing cleanup")

    if servers:
        server_id = getattr(servers[0], "id", None)
        if not server_id:
            raise RuntimeError(f"VM '{vm_name}' has no server ID")
        chi.server.delete_server(server_id)

    # Nova deletion is asynchronous. Verify absence before releasing the lease.
    deadline = time.monotonic() + 120
    while True:
        remaining_servers = matching_servers()
        if not remaining_servers:
            break
        if time.monotonic() >= deadline:
            raise RuntimeError(
                f"VM '{vm_name}' still exists; refusing reservation deletion"
            )
        time.sleep(5)

    leases = [
        lease for lease in chi.lease.list_leases()
        if getattr(lease, "name", None) == reservation_name
    ]

    if len(leases) > 1:
        raise RuntimeError(
            f"Multiple reservations named '{reservation_name}'; "
            "refusing cleanup"
        )

    if leases:
        if not getattr(leases[0], "id", None):
            raise RuntimeError(
                f"Reservation '{reservation_name}' has no ID"
            )
        leases[0].delete()


def verify_key_absent(key_name):
    """Refuse SSH-key upload if the exact key name already exists."""
    if not isinstance(key_name, str) or not key_name:
        raise ValueError("A non-empty SSH-key name is required")

    keypairs = chi.server.list_keypair()
    if any(getattr(key, "name", None) == key_name for key in keypairs):
        raise RuntimeError(
            f"SSH key '{key_name}' already exists; refusing upload"
        )


def cleanup_smoke_key(key_name, expected_public_key):
    """Delete a smoke-test SSH key only if its identity matches."""
    if not isinstance(key_name, str) or not key_name:
        raise ValueError("A non-empty SSH-key name is required")
    if not isinstance(expected_public_key, str) or not expected_public_key.strip():
        raise ValueError("Expected public-key content is required")

    matching_keys = [
        key for key in chi.server.list_keypair()
        if getattr(key, "name", None) == key_name
    ]

    if len(matching_keys) > 1:
        raise RuntimeError(
            f"Multiple SSH keys named '{key_name}'; refusing deletion"
        )

    if not matching_keys:
        return

    actual_key = getattr(matching_keys[0], "public_key", None)
    if not actual_key or actual_key.strip() != expected_public_key.strip():
        raise RuntimeError(
            f"SSH key '{key_name}' does not match the expected public key; "
            "refusing deletion"
        )

    chi.server.nova().keypairs.delete(key_name)


def verify_security_group_absent(group_name):
    """Refuse smoke-test startup if the security-group name is already used."""
    if not isinstance(group_name, str) or not group_name.strip():
        raise ValueError("A non-empty security-group name is required")

    groups = chi.network.list_security_groups(name_filter=group_name)
    if any(
        getattr(group, "name", None) == group_name
        for group in groups
    ):
        raise RuntimeError(
            f"Security group '{group_name}' already exists; "
            "refusing smoke-test startup"
        )


def cleanup_smoke_security_group(group_name, expected_description):
    """Delete a smoke-test security group only when its identity matches."""
    if not isinstance(group_name, str) or not group_name.strip():
        raise ValueError("A non-empty security-group name is required")
    if not isinstance(expected_description, str) or not expected_description.strip():
        raise ValueError("An expected security-group description is required")

    groups = chi.network.list_security_groups(name_filter=group_name)
    matching_groups = [
        group for group in groups
        if getattr(group, "name", None) == group_name
    ]

    if len(matching_groups) > 1:
        raise RuntimeError(
            f"Multiple security groups named '{group_name}'; refusing cleanup"
        )

    if not matching_groups:
        return

    group = matching_groups[0]

    if getattr(group, "description", None) != expected_description:
        raise RuntimeError(
            f"Security group '{group_name}' has an unexpected description; "
            "refusing deletion"
        )

    group_id = getattr(group, "id", None)
    if not group_id:
        raise RuntimeError(
            f"Security group '{group_name}' has no ID; refusing deletion"
        )

    chi.network.neutron().delete_security_group(group_id)
