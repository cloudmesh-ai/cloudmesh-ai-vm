"""Utility functions to handle floating IP (FIP) allocation, reservation, and
release for OpenStack based providers (Jetstream, Chameleon, generic OpenStack).

The functions are deliberately lightweight and use the OpenStack SDK connection
object passed in by the caller.  This keeps them provider‑agnostic – they can be
re‑used by any manager that works with an ``openstack.connection.Connection``
instance.

All functions raise ``Exception`` on fatal errors so that callers can decide
whether to abort the VM creation workflow or retry.  The retry/back‑off logic
is implemented in ``allocate_fip_with_retry`` which is used by the provider
implementation.
"""

from __future__ import annotations

import random
import time
from typing import List, Optional

# The OpenStack SDK ``Connection`` class is only imported lazily inside the
# functions to avoid pulling heavy dependencies when the module is imported on
# platforms that do not have OpenStack installed.


def list_unassigned_fips(conn) -> List[object]:
    """Return a list of floating IP objects that are not attached to any port.

    ``conn`` must be an ``openstack.connection.Connection``.  The function
    iterates over all floating IPs visible to the project and filters those
    whose ``port_id`` attribute is ``None`` or an empty string.
    """
    # ``conn.network.ips()`` returns a generator of ``FloatingIP`` objects.
    unassigned = []
    for fip in conn.network.ips():
        # Some SDK objects expose ``port_id`` as ``None`` when unattached.
        if not getattr(fip, "port_id", None):
            unassigned.append(fip)
    return unassigned


def lock_and_select_fip(fip_list: List[object]) -> object:
    """Select a floating IP from *fip_list* and perform a lightweight lock.

    The simple implementation picks the first entry.  A real implementation
    could add a tag or a custom attribute to signal that the IP is in use.
    For the purpose of this plan we return the selected FIP object unchanged.
    """
    if not fip_list:
        raise RuntimeError("No unassigned floating IPs available to lock.")
    # In a production environment you would apply a tag or metadata here to
    # prevent race conditions.  The OpenStack SDK does not provide a direct
    # "lock" operation, so we rely on the allocation retry logic to mitigate
    # contention.
    return fip_list[0]


def allocate_fip_with_retry(
    conn,
    max_retries: int = 4,
    base_delay: int = 2,
):
    """Create a new floating IP, retrying with exponential back‑off.

    Parameters
    ----------
    conn: openstack.connection.Connection
        Authenticated connection used to call ``network.create_ip``.
    max_retries: int, optional
        Number of allocation attempts before giving up.
    base_delay: int, optional
        Base delay in seconds for exponential back‑off.  The actual wait for
        attempt *n* is ``base_delay * (2 ** (n‑1))`` plus a small jitter.
    """
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            return conn.network.create_ip()
        except Exception as e:  # pragma: no cover – exercised via tests
            last_error = e
            if attempt == max_retries:
                break
            # exponential back‑off with jitter to reduce contention
            delay = base_delay * (2 ** (attempt - 1)) + random.uniform(0, 1)
            time.sleep(delay)
    # If we exit the loop without returning, raise the last exception.
    raise RuntimeError(
        f"Failed to allocate a new floating IP after {max_retries} attempts"
    ) from last_error


def release_fip(conn, fip) -> None:
    """Release or delete a floating IP.

    The SDK provides ``delete_ip``; if the IP is already attached we first
    dissociate it by clearing the ``port_id`` (this is a no‑op for already free
    IPs).  Errors are swallowed – releasing a FIP should never abort the caller
    workflow.
    """
    try:
        # ``delete_ip`` handles both attached and unattached IPs.
        conn.network.delete_ip(fip)
    except Exception:  # pragma: no cover – best‑effort cleanup
        pass
