"""Unit tests for Chameleon smoke-test resource safety."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from tests.smoke.chameleon_cleanup import verify_resources_absent


@pytest.fixture
def mock_chi():
    with patch("tests.smoke.chameleon_cleanup.chi") as chi:
        chi.server.nova.return_value.servers.list.return_value = []
        chi.lease.list_leases.return_value = []
        yield chi


def test_preflight_accepts_unused_names(mock_chi):
    verify_resources_absent("smoke-test-123")
    mock_chi.server.nova.return_value.servers.list.assert_called_once_with(
        limit=-1
    )
    mock_chi.lease.list_leases.assert_called_once()


def test_preflight_rejects_existing_vm(mock_chi):
    mock_chi.server.nova.return_value.servers.list.return_value = [
        SimpleNamespace(name="smoke-test-123")
    ]

    with pytest.raises(RuntimeError, match="already exists"):
        verify_resources_absent("smoke-test-123")

    mock_chi.lease.list_leases.assert_not_called()


def test_preflight_rejects_existing_reservation(mock_chi):
    mock_chi.lease.list_leases.return_value = [
        SimpleNamespace(name="res-smoke-test-123")
    ]

    with pytest.raises(RuntimeError, match="Reservation.*already exists"):
        verify_resources_absent("smoke-test-123")


def test_preflight_propagates_api_failure(mock_chi):
    mock_chi.server.nova.return_value.servers.list.side_effect = (
        RuntimeError("Cloud API unavailable")
    )

    with pytest.raises(RuntimeError, match="Cloud API unavailable"):
        verify_resources_absent("smoke-test-123")


def test_preflight_propagates_reservation_api_failure(mock_chi):
    mock_chi.lease.list_leases.side_effect = RuntimeError(
        "Reservation API unavailable"
    )

    with pytest.raises(RuntimeError, match="Reservation API unavailable"):
        verify_resources_absent("smoke-test-123")


from tests.smoke.chameleon_cleanup import cleanup_smoke_resources


def test_cleanup_when_no_resources_exist(mock_chi):
    cleanup_smoke_resources("smoke-test-123")
    mock_chi.server.delete_server.assert_not_called()


def test_cleanup_deletes_exact_vm_and_reservation(mock_chi):
    server = SimpleNamespace(name="smoke-test-123", id="server-123")
    lease = SimpleNamespace(
        name="res-smoke-test-123",
        id="lease-123",
        delete=MagicMock(),
    )

    mock_chi.server.nova.return_value.servers.list.side_effect = [
        [server],
        [],
    ]
    mock_chi.lease.list_leases.return_value = [lease]

    cleanup_smoke_resources("smoke-test-123")

    mock_chi.server.delete_server.assert_called_once_with("server-123")
    lease.delete.assert_called_once()


def test_cleanup_preserves_unrelated_resources(mock_chi):
    unrelated_server = SimpleNamespace(name="production-vm", id="prod-123")
    unrelated_lease = SimpleNamespace(
        name="res-production-vm",
        id="prod-lease",
        delete=MagicMock(),
    )

    mock_chi.server.nova.return_value.servers.list.return_value = [
        unrelated_server
    ]
    mock_chi.lease.list_leases.return_value = [unrelated_lease]

    cleanup_smoke_resources("smoke-test-123")

    mock_chi.server.delete_server.assert_not_called()
    unrelated_lease.delete.assert_not_called()


def test_cleanup_rejects_duplicate_vms(mock_chi):
    mock_chi.server.nova.return_value.servers.list.return_value = [
        SimpleNamespace(name="smoke-test-123", id="server-1"),
        SimpleNamespace(name="smoke-test-123", id="server-2"),
    ]

    with pytest.raises(RuntimeError, match="Multiple VMs"):
        cleanup_smoke_resources("smoke-test-123")

    mock_chi.server.delete_server.assert_not_called()


def test_cleanup_rejects_duplicate_reservations(mock_chi):
    mock_chi.lease.list_leases.return_value = [
        SimpleNamespace(name="res-smoke-test-123", id="lease-1"),
        SimpleNamespace(name="res-smoke-test-123", id="lease-2"),
    ]

    with pytest.raises(RuntimeError, match="Multiple reservations"):
        cleanup_smoke_resources("smoke-test-123")


def test_cleanup_refuses_reservation_deletion_if_vm_remains(mock_chi):
    server = SimpleNamespace(name="smoke-test-123", id="server-123")
    mock_chi.server.nova.return_value.servers.list.return_value = [server]

    with patch(
        "tests.smoke.chameleon_cleanup.time.monotonic",
        side_effect=[0, 121],
    ):
        with pytest.raises(RuntimeError, match="still exists"):
            cleanup_smoke_resources("smoke-test-123")

    mock_chi.lease.list_leases.assert_not_called()


def test_cleanup_waits_for_vm_deletion_before_releasing_lease(mock_chi):
    server = SimpleNamespace(name="smoke-test-123", id="server-123")
    lease = SimpleNamespace(
        name="res-smoke-test-123",
        id="lease-123",
        delete=MagicMock(),
    )

    # VM exists initially, remains during the first check,
    # and disappears on the next check.
    mock_chi.server.nova.return_value.servers.list.side_effect = [
        [server],
        [server],
        [],
    ]
    mock_chi.lease.list_leases.return_value = [lease]

    with patch(
        "tests.smoke.chameleon_cleanup.time.sleep"
    ) as mock_sleep:
        cleanup_smoke_resources("smoke-test-123")

    mock_chi.server.delete_server.assert_called_once_with("server-123")
    mock_sleep.assert_called_once_with(5)
    lease.delete.assert_called_once()


from tests.smoke.chameleon_cleanup import verify_key_absent


def test_key_preflight_accepts_unused_name(mock_chi):
    mock_chi.server.list_keypair.return_value = [
        SimpleNamespace(name="existing-production-key")
    ]

    verify_key_absent("smoke-key-abc123")

    mock_chi.server.list_keypair.assert_called_once()


def test_key_preflight_rejects_existing_name(mock_chi):
    mock_chi.server.list_keypair.return_value = [
        SimpleNamespace(name="smoke-key-abc123")
    ]

    with pytest.raises(RuntimeError, match="already exists"):
        verify_key_absent("smoke-key-abc123")


def test_key_preflight_propagates_api_failure(mock_chi):
    mock_chi.server.list_keypair.side_effect = RuntimeError(
        "Keypair API unavailable"
    )

    with pytest.raises(RuntimeError, match="Keypair API unavailable"):
        verify_key_absent("smoke-key-abc123")


from tests.smoke.chameleon_cleanup import cleanup_smoke_key


def test_key_cleanup_deletes_matching_key(mock_chi):
    mock_chi.server.list_keypair.return_value = [
        SimpleNamespace(name="smoke-key-abc123", public_key="ssh-ed25519 AAAATEST")
    ]

    cleanup_smoke_key("smoke-key-abc123", "ssh-ed25519 AAAATEST")

    mock_chi.server.nova.return_value.keypairs.delete.assert_called_once_with(
        "smoke-key-abc123"
    )


def test_key_cleanup_skips_missing_key(mock_chi):
    mock_chi.server.list_keypair.return_value = []

    cleanup_smoke_key("smoke-key-abc123", "ssh-ed25519 AAAATEST")

    mock_chi.server.nova.return_value.keypairs.delete.assert_not_called()


def test_key_cleanup_rejects_mismatched_public_key(mock_chi):
    mock_chi.server.list_keypair.return_value = [
        SimpleNamespace(name="smoke-key-abc123", public_key="ssh-ed25519 DIFFERENT")
    ]

    with pytest.raises(RuntimeError, match="does not match"):
        cleanup_smoke_key("smoke-key-abc123", "ssh-ed25519 AAAATEST")

    mock_chi.server.nova.return_value.keypairs.delete.assert_not_called()


def test_key_cleanup_rejects_duplicate_names(mock_chi):
    mock_chi.server.list_keypair.return_value = [
        SimpleNamespace(name="smoke-key-abc123", public_key="ssh-ed25519 AAAATEST"),
        SimpleNamespace(name="smoke-key-abc123", public_key="ssh-ed25519 AAAATEST"),
    ]

    with pytest.raises(RuntimeError, match="Multiple SSH keys"):
        cleanup_smoke_key("smoke-key-abc123", "ssh-ed25519 AAAATEST")

    mock_chi.server.nova.return_value.keypairs.delete.assert_not_called()


def test_key_cleanup_propagates_api_failure(mock_chi):
    mock_chi.server.list_keypair.side_effect = RuntimeError("Nova unavailable")

    with pytest.raises(RuntimeError, match="Nova unavailable"):
        cleanup_smoke_key("smoke-key-abc123", "ssh-ed25519 AAAATEST")

    mock_chi.server.nova.return_value.keypairs.delete.assert_not_called()


def test_security_group_preflight_rejects_existing_group():
    from unittest.mock import patch
    from types import SimpleNamespace
    from tests.smoke.chameleon_cleanup import verify_security_group_absent
    import pytest

    with patch("tests.smoke.chameleon_cleanup.chi") as mock_chi:
        mock_chi.network.list_security_groups.return_value = [
            SimpleNamespace(name="smoke-test-sg")
        ]

        with pytest.raises(RuntimeError, match="already exists"):
            verify_security_group_absent("smoke-test-sg")


def test_security_group_cleanup_deletes_exact_match():
    from unittest.mock import patch
    from types import SimpleNamespace
    from tests.smoke.chameleon_cleanup import cleanup_smoke_security_group

    with patch("tests.smoke.chameleon_cleanup.chi") as mock_chi:
        mock_chi.network.list_security_groups.return_value = [
            SimpleNamespace(
                name="smoke-test-sg",
                description="Smoke test security group",
                id="sg-123",
            )
        ]

        cleanup_smoke_security_group(
            "smoke-test-sg", "Smoke test security group"
        )

        mock_chi.network.neutron.return_value.delete_security_group.assert_called_once_with(
            "sg-123"
        )


def test_security_group_cleanup_refuses_description_mismatch():
    from unittest.mock import patch
    from types import SimpleNamespace
    from tests.smoke.chameleon_cleanup import cleanup_smoke_security_group
    import pytest

    with patch("tests.smoke.chameleon_cleanup.chi") as mock_chi:
        mock_chi.network.list_security_groups.return_value = [
            SimpleNamespace(
                name="smoke-test-sg",
                description="Unrelated security group",
                id="sg-123",
            )
        ]

        with pytest.raises(RuntimeError, match="unexpected description"):
            cleanup_smoke_security_group(
                "smoke-test-sg", "Smoke test security group"
            )

        mock_chi.network.neutron.assert_not_called()
