"""Unit tests for the floating‑IP utility helpers.

The helpers in ``cloudmesh.ai.vm.fip_utils`` are deliberately lightweight and
operate on an OpenStack SDK ``Connection`` object.  To keep the tests fast and
environment‑independent we mock the ``Connection`` and its ``network`` attribute.
"""

from unittest.mock import MagicMock, call
import pytest

from cloudmesh.ai.vm.fip_utils import (
    list_unassigned_fips,
    lock_and_select_fip,
    allocate_fip_with_retry,
    release_fip,
)


class DummyFIP:
    """Simple floating‑IP mock object used by the tests."""

    def __init__(self, address: str, port_id: str | None = None):
        self.floating_ip_address = address
        self.port_id = port_id


def test_list_unassigned_fips_filters_assigned_ips():
    # Create a fake connection whose ``network.ips`` method returns a mix of
    # assigned and unassigned floating IPs.
    conn = MagicMock()
    conn.network.ips.return_value = [
        DummyFIP("1.2.3.4", port_id="port-1"),
        DummyFIP("5.6.7.8"),
        DummyFIP("9.10.11.12"),
    ]

    unassigned = list_unassigned_fips(conn)
    # Only the IPs without ``port_id`` should be returned.
    assert len(unassigned) == 2
    assert all(fip.port_id is None for fip in unassigned)
    assert {fip.floating_ip_address for fip in unassigned} == {"5.6.7.8", "9.10.11.12"}


def test_lock_and_select_fip_returns_first_item_and_errors_on_empty():
    fip_list = [DummyFIP("1.1.1.1"), DummyFIP("2.2.2.2")]
    selected = lock_and_select_fip(fip_list)
    assert selected is fip_list[0]

    # An empty list should raise a RuntimeError.
    with pytest.raises(RuntimeError):
        lock_and_select_fip([])


def test_allocate_fip_with_retry_success_and_backoff(monkeypatch):
    # Patch ``time.sleep`` to avoid real delays during the test.
    monkeypatch.setattr("time.sleep", lambda _: None)

    conn = MagicMock()
    # Simulate two failures followed by a success.
    side_effects = [Exception("temp failure"), Exception("temp failure"), DummyFIP("3.3.3.3")]
    conn.network.create_ip.side_effect = side_effects

    fip = allocate_fip_with_retry(conn, max_retries=4, base_delay=1)
    assert isinstance(fip, DummyFIP)
    assert fip.floating_ip_address == "3.3.3.3"
    # Ensure ``create_ip`` was called three times (two failures + one success).
    assert conn.network.create_ip.call_count == 3


def test_allocate_fip_with_retry_exhausts_and_raises():
    conn = MagicMock()
    conn.network.create_ip.side_effect = Exception("always fails")
    with pytest.raises(RuntimeError) as exc:
        allocate_fip_with_retry(conn, max_retries=2, base_delay=1)
    assert "Failed to allocate a new floating IP" in str(exc.value)
    # Should have attempted exactly ``max_retries`` times.
    assert conn.network.create_ip.call_count == 2


def test_release_fip_calls_delete_and_swallows_errors(monkeypatch):
    conn = MagicMock()
    # ``delete_ip`` will raise an exception; release_fip should swallow it.
    conn.network.delete_ip.side_effect = Exception("delete error")
    fip = DummyFIP("4.4.4.4")
    # No exception should propagate.
    release_fip(conn, fip)
    conn.network.delete_ip.assert_called_once_with(fip)
