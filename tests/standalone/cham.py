#!/usr/bin/env python
"""
Launch a VM on Chameleon KVM@TACC using a flavor-based Blazar lease.

Workflow
  1. Connect via clouds.yaml
  2. Create a *flavor:instance* lease (the reservation type KVM@TACC uses)
  3. Wait for the lease to become ACTIVE and pull out the reserved flavor
  4. Ensure keypair, SSH security-group rule, and a floating IP
  5. Boot the VM with the reserved flavor, attach the floating IP
  6. Wait for SSH and run a test command
  7. Optionally tear everything down (always on failure)

Only depends on openstacksdk (no python-chi needed).
"""

import argparse
import socket
import subprocess
import sys
import time
import traceback
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import openstack

TERMINAL_LEASE_STATES = {"ERROR", "FAILED", "TERMINATED", "DELETED"}

FLAVOR="m1.medium"

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def log(icon: str, msg: str) -> None:
    print(f"{icon}  {msg}", flush=True)


def die(msg: str) -> None:
    sys.exit(f"❌ {msg}")


class Tracker:
    """Remembers what this run created so we can clean up precisely that."""

    def __init__(self):
        self.lease_id = None
        self.server = None
        self.fip = None
        self.created_keypair = None


# --------------------------------------------------------------------------- #
# Connection / Blazar
# --------------------------------------------------------------------------- #
def get_connection(cloud: str) -> openstack.connection.Connection:
    try:
        conn = openstack.connect(cloud=cloud)
        conn.authorize()
        return conn
    except Exception as exc:
        die(f"Failed to connect to cloud '{cloud}': {exc}")


def get_blazar_url(conn) -> str:
    for svc in ("reservation", "reservations", "climate"):
        try:
            url = conn.session.get_endpoint(service_type=svc, interface="public")
            if url:
                return url.rstrip("/")
        except Exception:
            continue
    die("Blazar (reservation) endpoint not found in the Keystone catalog. "
        "Is this a KVM@TACC cloud entry?")


def blazar(conn, method: str, url: str, **kw):
    """Blazar request with retries for transient connection drops."""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # connect_retries is passed to the underlying keystoneauth session
            resp = conn.session.request(url, method, raise_exc=False, connect_retries=max_retries, **kw)
            if resp.status_code >= 400:
                # We don't retry 4xx errors (client errors), only 5xx or connection drops
                if resp.status_code < 500:
                    raise RuntimeError(f"Blazar {method} {url} -> HTTP {resp.status_code}: {resp.text}")
            return resp.json() if resp.content else {}
        except (socket.error, RuntimeError) as e:
            if attempt == max_retries - 1:
                raise RuntimeError(f"Blazar {method} {url} failed after {max_retries} attempts: {e}")
            time.sleep(2 ** attempt)  # Exponential backoff


# --------------------------------------------------------------------------- #
# Flavor lease
# --------------------------------------------------------------------------- #
def find_flavor(conn, identifier: str):
    flavor = conn.compute.find_flavor(identifier)
    if not flavor:
        names = sorted(f.name for f in conn.compute.flavors())
        die(f"Flavor '{identifier}' not found. Available: {', '.join(names)}")
    return flavor


def create_flavor_lease(conn, blazar_url, name, flavor, count, hours) -> str:
    """
    Create a flavor:instance lease. Reusing an existing lease name is avoided
    by appending a timestamp, since Blazar lease names must be unique.
    """
    unique_name = f"{name}-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}"
    end = datetime.now(timezone.utc) + timedelta(hours=hours)

    payload = {
        "name": unique_name,
        "start_date": "now",
        "end_date": end.strftime("%Y-%m-%d %H:%M"),
        "reservations": [
            {
                "resource_type": "flavor:instance",
                "flavor_id": flavor.id,
                "amount": count,
                "affinity": None,
            }
        ],
        "events": [],
    }

    log("", f"Creating flavor lease '{unique_name}': {count}x {flavor.name} for {hours}h (UTC end {payload['end_date']})")
    lease = blazar(conn, "POST", f"{blazar_url}/leases", json=payload).get("lease", {})
    lease_id = lease.get("id")
    if not lease_id:
        die(f"Lease creation returned no ID: {lease}")
    log("✅", f"Lease submitted: {lease_id}")
    return lease_id


def wait_for_lease(conn, blazar_url, lease_id, timeout=600, interval=10) -> dict:
    log("", f"Waiting for lease to become ACTIVE (up to {timeout}s)...")
    deadline = time.time() + timeout
    last = None
    consecutive_failures = 0
    max_failures = 5

    while time.time() < deadline:
        try:
            lease = blazar(conn, "GET", f"{blazar_url}/leases/{lease_id}").get("lease", {})
            consecutive_failures = 0  # Reset counter on successful response

            status = lease.get("status", "").upper()
            if status != last:
                log("   ", f"Lease status: {status}")
                last = status
            if status == "ACTIVE":
                log("✅", "Lease is ACTIVE")
                return lease
            if status in TERMINAL_LEASE_STATES:
                raise RuntimeError(f"Lease entered terminal state {status} (degraded={lease.get('degraded')})")
        except Exception as e:
            consecutive_failures += 1
            log("   ⚠️", f"Transient poll error ({consecutive_failures}/{max_failures}): {e}")
            if consecutive_failures >= max_failures:
                raise RuntimeError(f"Lease polling failed after {max_failures} consecutive attempts: {e}")

        time.sleep(interval)
    raise TimeoutError(f"Lease {lease_id} not ACTIVE after {timeout}s")


def get_reserved_flavor(conn, lease: dict):
    """
    A flavor reservation creates a *new* Nova flavor tied to the reservation.
    Servers must be booted with that flavor (not the base m1.* flavor).
    Returns (reservation_id, reserved_flavor).
    """
    reservations = [r for r in lease.get("reservations", []) if r.get("resource_type") == "flavor:instance"]
    if not reservations:
        raise RuntimeError("Lease has no flavor:instance reservation")

    res = reservations[0]
    res_id = res["id"]

    # Preferred: resource_id is the reserved flavor's ID
    flavor = None
    if res.get("resource_id"):
        flavor = conn.compute.find_flavor(res["resource_id"])
    # Fallback: reserved flavors are named "reservation:<reservation_id>"
    if not flavor:
        flavor = conn.compute.find_flavor(f"reservation:{res_id}")
    if not flavor:
        raise RuntimeError(f"Could not locate reserved flavor for reservation {res_id}")

    log("", f"Reservation {res_id} -> reserved flavor '{flavor.name}' ({flavor.id})")
    return res_id, flavor


# --------------------------------------------------------------------------- #
# Supporting resources
# --------------------------------------------------------------------------- #
def ensure_keypair(conn, name: str, pub_path: Path, tracker: Tracker) -> str:
    if conn.compute.find_keypair(name):
        log("✅", f"Keypair '{name}' already exists")
        return name
    if not pub_path.is_file():
        die(f"Public key not found at {pub_path} (use --keyfile)")
    log("", f"Creating keypair '{name}' from {pub_path}")
    conn.compute.create_keypair(name=name, public_key=pub_path.read_text().strip())
    tracker.created_keypair = name
    return name


def find_image(conn, identifier: str):
    img = conn.image.find_image(identifier)
    if img:
        return img
    images = list(conn.image.images())
    for fallback in ("CC-Ubuntu22.04", "CC-Ubuntu24.04", "CC-Ubuntu20.04"):
        match = next((i for i in images if i.name == fallback), None)
        if match:
            log("⚠️ ", f"Image '{identifier}' not found, using '{match.name}'")
            return match
    die(f"Image '{identifier}' not found.")


def find_network(conn, identifier: str):
    net = conn.network.find_network(identifier)
    if net:
        return net
    for candidate in ("sharednet1", "project_net"):
        net = conn.network.find_network(candidate)
        if net:
            log("⚠️ ", f"Network '{identifier}' not found, using '{net.name}'")
            return net
    die(f"Network '{identifier}' not found.")


def ensure_ssh_rule(conn, secgroup_name: str):
    sg = conn.network.find_security_group(secgroup_name)
    if not sg:
        die(f"Security group '{secgroup_name}' not found.")
    for rule in conn.network.security_group_rules(security_group_id=sg.id):
        if (rule.direction == "ingress" and rule.protocol == "tcp"
                and (rule.port_range_min or 0) <= 22 <= (rule.port_range_max or 65535)
                and rule.ether_type == "IPv4"):
            return sg
    log(" ", f"Adding SSH (22/tcp) ingress rule to '{sg.name}'")
    try:
        conn.network.create_security_group_rule(
            security_group_id=sg.id, direction="ingress", ethertype="IPv4",
            protocol="tcp", port_range_min=22, port_range_max=22, remote_ip_prefix="0.0.0.0/0",
        )
    except Exception as e:
        if "already exists" in str(e).lower():
            log("   ", "Security group rule already exists (ignoring)")
        else:
            log("⚠️ ", f"Rule creation warning: {e}")
    return sg


def get_floating_ip(conn, ext_net_name: str, tracker: Tracker):
    """Reuse an unassigned floating IP if one exists, otherwise allocate."""
    try:
        for fip in conn.network.ips():
            if fip.status == "DOWN" and not fip.port_id:
                log(" ", f"Reusing free floating IP {fip.floating_ip_address}")
                return fip
    except Exception as e:
        log("⚠️ ", f"Error listing floating IPs: {e}")

    ext = conn.network.find_network(ext_net_name) or next(
        (n for n in conn.network.networks() if n.is_router_external), None)
    if not ext:
        die(f"External network '{ext_net_name}' not found.")
    log("", f"Allocating floating IP from '{ext.name}'")
    try:
        fip = conn.network.create_ip(floating_network_id=ext.id)
        tracker.fip = fip  # only tracked for cleanup when *we* created it
        log("✅", f"Allocated {fip.floating_ip_address}")
        return fip
    except Exception as e:
        die(f"Failed to allocate floating IP: {e}")


# --------------------------------------------------------------------------- #
# Server
# --------------------------------------------------------------------------- #
def boot_server(conn, args, image, flavor, network, sg, keypair, reservation_id):
    max_boot_attempts = 10
    for boot_attempt in range(max_boot_attempts):
        log("", f"Booting '{args.name}' (Attempt {boot_attempt+1}/{max_boot_attempts}, flavor={flavor.name}, image={image.name})")

        server = None
        try:
            # 1. Create the server (with retries for transient connection drops)
            create_max_attempts = 3
            for create_attempt in range(create_max_attempts):
                try:
                    server = conn.compute.create_server(
                        name=args.name,
                        image_id=image.id,
                        flavor_id=flavor.id,
                        networks=[{"uuid": network.id}],
                        security_groups=[{"name": sg.name}],
                        key_name=keypair,
                        scheduler_hints={"reservation": reservation_id},
                        metadata={"reservation": reservation_id},
                    )
                    break
                except Exception as e:
                    if "RemoteDisconnected" in str(e) or "Connection aborted" in str(e):
                        if create_attempt < create_max_attempts - 1:
                            log("   ⚠️", f"Transient connection drop during creation ({create_attempt+1}/{create_max_attempts}). Retrying...")
                            time.sleep(10)
                            continue
                    raise e

            # 2. Wait for server to become ACTIVE (with retries for transient connection drops)
            wait_max_attempts = 5
            for wait_attempt in range(wait_max_attempts):
                try:
                    server = conn.compute.wait_for_server(server, status="ACTIVE", failures=["ERROR"],
                                                          interval=10, wait=args.wait)
                    log("✅", "Server is ACTIVE")
                    return server
                except Exception as e:
                    if "RemoteDisconnected" in str(e) or "Connection aborted" in str(e):
                        if wait_attempt < wait_max_attempts - 1:
                            log("   ⚠️", f"Transient connection drop while waiting for server ({wait_attempt+1}/{wait_max_attempts}). Retrying...")
                            time.sleep(10)
                            continue

                    # Handle ResourceFailure (server transitioned to ERROR)
                    if "transitioned to failure state ERROR" in str(e):
                        try:
                            sid = server.id if hasattr(server, 'id') else None
                            if not sid:
                                import re
                                match = re.search(r"Server:([a-f0-9-]+)", str(e))
                                if match:
                                    sid = match.group(1)

                            if sid:
                                server_info = conn.compute.get_server(sid)
                                # The fault object is usually a dict or an object with 'message'
                                fault = getattr(server_info, 'fault', None)
                                fault_msg = ""
                                if isinstance(fault, dict):
                                    fault_msg = fault.get('message', '')
                                elif fault:
                                    fault_msg = getattr(fault, 'message', '')

                                if "No valid host" in fault_msg or (isinstance(fault, dict) and fault.get('code') == 500):
                                    log("", f"NoValidHost detected: {fault_msg}")
                                    log("", "Retrying entire boot process to find a different host...")
                                    conn.compute.delete_server(sid)
                                    conn.compute.wait_for_delete(sid, wait=60)
                                    raise RuntimeError("NO_VALID_HOST")
                        except Exception as fetch_err:
                            log("⚠️ ", f"Could not fetch fault details: {fetch_err}")

                    raise e
        except RuntimeError as e:
            if str(e) == "NO_VALID_HOST":
                if boot_attempt < max_boot_attempts - 1:
                    time.sleep(20)
                    continue
            raise e
        except Exception as e:
            if server and hasattr(server, 'id'):
                try:
                    conn.compute.delete_server(server.id)
                except: pass
            raise e

    raise RuntimeError(f"Failed to boot server after {max_boot_attempts} attempts.")


def attach_floating_ip(conn, server, fip):
    ports = list(conn.network.ports(device_id=server.id))
    if not ports:
        raise RuntimeError("Server has no ports; cannot attach floating IP")
    conn.network.update_ip(fip, port_id=ports[0].id)
    log("", f"Attached {fip.floating_ip_address} to {server.name}")


def wait_for_port(ip: str, port: int = 22, timeout: int = 180) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((ip, port), timeout=5):
                return True
        except OSError:
            time.sleep(5)
    return False


def test_ssh(user, ip, key: Path, command, timeout) -> bool:
    log("", f"Testing SSH to {user}@{ip} (running '{command}')")
    if not key.is_file():
        log("⚠️ ", f"Private key {key} not found; skipping SSH test")
        return False
    if not wait_for_port(ip, 22, timeout):
        log("❌", f"Port 22 on {ip} not reachable within {timeout}s")
        return False

    cmd = ["ssh", "-i", str(key), "-o", "StrictHostKeyChecking=no",
           "-o", "UserKnownHostsFile=/dev/null", "-o", "ConnectTimeout=5",
           "-o", "BatchMode=yes", f"{user}@{ip}", command]
    deadline = time.time() + timeout
    err = ""
    while time.time() < deadline:
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            log("✅", f"SSH OK. Output:\n{res.stdout.strip()}")
            return True
        err = res.stderr.strip()
        time.sleep(5)
    log("❌", f"SSH failed within {timeout}s. Last error: {err}")
    return False


# --------------------------------------------------------------------------- #
# Cleanup
# --------------------------------------------------------------------------- #
def cleanup(conn, blazar_url, t: Tracker):
    log("", "Cleaning up resources created by this run...")
    try:
        if t.fip:
            conn.network.update_ip(t.fip, port_id=None)
    except Exception:
        pass
    if t.server:
        try:
            conn.compute.delete_server(t.server, ignore_missing=True)
            conn.compute.wait_for_delete(t.server, wait=180)
            log("   ", "Server deleted")
        except Exception as e:
            log("⚠️ ", f"Server delete: {e}")
    if t.fip:
        try:
            conn.network.delete_ip(t.fip, ignore_missing=True)
            log("   ", "Floating IP released")
        except Exception as e:
            log("⚠️ ", f"Floating IP delete: {e}")
    if t.created_keypair:
        try:
            conn.compute.delete_keypair(t.created_keypair, ignore_missing=True)
            log("   ", "Keypair deleted")
        except Exception as e:
            log("⚠️ ", f"Keypair delete: {e}")
    if t.lease_id:
        try:
            blazar(conn, "DELETE", f"{blazar_url}/leases/{t.lease_id}")
            log("   ", "Lease deleted")
        except Exception as e:
            log("⚠️ ", f"Lease delete: {e}")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def parse_args():
    p = argparse.ArgumentParser(description="Launch a Chameleon KVM@TACC VM using a flavor lease.")
    p.add_argument("--cloud", default="chameleon", help="clouds.yaml entry (default: chameleon)")
    p.add_argument("--name", default="gregor-chameleon-vm")
    p.add_argument("--lease-name", default="kvm-flavor-lease", help="Lease name prefix (timestamp appended)")
    p.add_argument("--duration", type=float, default=1, help="Lease duration in hours (default: 1)")
    p.add_argument("--count", type=int, default=1, help="Number of instances to reserve")
    p.add_argument("--lease-id", help="Use an existing ACTIVE lease instead of creating one")
    p.add_argument("--image", default="CC-Ubuntu22.04")
    p.add_argument("--flavor", default=FLAVOR, help="Base flavor to reserve")
    p.add_argument("--network", default="sharednet1")
    p.add_argument("--secgroup", default="default")
    p.add_argument("--keypair", default="chameleon-tmp-key")
    p.add_argument("--keyfile", default=str(Path.home() / ".ssh/id_rsa.pub"))
    p.add_argument("--privkey", default=str(Path.home() / ".ssh/id_rsa"))
    p.add_argument("--user", default="cc")
    p.add_argument("--command", default="uname -a")
    p.add_argument("--ext-net", default="public")
    p.add_argument("--wait", type=int, default=600, help="Seconds to wait for VM ACTIVE")
    p.add_argument("--lease-timeout", type=int, default=600, help="Seconds to wait for lease ACTIVE")
    p.add_argument("--ssh-timeout", type=int, default=180)
    p.add_argument("--cleanup", action="store_true", help="Tear down everything after the SSH test")
    p.add_argument("--keep", action="store_true", help="Do not delete the VM on failure")
    return p.parse_args()


def main():
    args = parse_args()
    args.name = f"{args.name}-{uuid.uuid4().hex[:8]}"
    t = Tracker()

    log("", f"Connecting to '{args.cloud}'...")
    conn = get_connection(args.cloud)
    log("", f"Region: {conn.config.region_name or 'unknown'}")
    blazar_url = get_blazar_url(conn)
    log("", f"Blazar endpoint: {blazar_url}")

    ok = False
    try:
        # 1. Lease (flavor reservation)
        if args.lease_id:
            lease = wait_for_lease(conn, blazar_url, args.lease_id, timeout=args.lease_timeout)
        else:
            base_flavor = find_flavor(conn, args.flavor)
            t.lease_id = create_flavor_lease(conn, blazar_url, args.lease_name,
                                             base_flavor, args.count, args.duration)
            lease = wait_for_lease(conn, blazar_url, t.lease_id, timeout=args.lease_timeout)
        reservation_id, reserved_flavor = get_reserved_flavor(conn, lease)

        # 2. Supporting resources
        keypair = ensure_keypair(conn, args.keypair, Path(args.keyfile), t)
        image = find_image(conn, args.image)
        network = find_network(conn, args.network)
        sg = ensure_ssh_rule(conn, args.secgroup)
        fip = get_floating_ip(conn, args.ext_net, t)

        # 3. Boot and attach
        t.server = boot_server(conn, args, image, reserved_flavor, network, sg, keypair, reservation_id)
        attach_floating_ip(conn, t.server, fip)

        # 4. Verify
        user = args.user
        if image.name.startswith("CC-"):
            user = "cc"
            if user != args.user:
                log("", f"Image starts with 'CC-', automatically using user '{user}'")

        priv = Path(args.privkey)
        if not priv.is_file() and args.keyfile.endswith(".pub"):
            alt = Path(args.keyfile[:-4])
            priv = alt if alt.is_file() else priv
        ok = test_ssh(user, fip.floating_ip_address, priv, args.command, args.ssh_timeout)

        print("\n" + "=" * 54)
        print("DEPLOYMENT COMPLETE" if ok else "DEPLOYED (SSH test did not pass)")
        print("=" * 54)
        print(f"  ssh -i {priv} {args.user}@{fip.floating_ip_address}")
        if not args.cleanup:
            print("\nCleanup when finished:")
            print(f"  openstack server delete {t.server.id}")
            print(f"  openstack floating ip delete {fip.id}")
            if t.lease_id:
                print(f"  openstack reservation lease delete {t.lease_id}")
    except KeyboardInterrupt:
        log("⚠️ ", "Interrupted")
        cleanup(conn, blazar_url, t)
        sys.exit(130)
    except Exception as exc:
        log("❌", f"Failed: {exc}")
        # Print the full traceback for easier debugging
        print("\n--- Traceback ---")
        traceback.print_exc()
        print("-----------------\n")
        cleanup(conn, blazar_url, t)
        sys.exit(1)

    if args.cleanup:
        cleanup(conn, blazar_url, t)
    sys.exit(0 if ok else 2)


if __name__ == "__main__":
    main()
