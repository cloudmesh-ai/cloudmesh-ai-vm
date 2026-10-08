#!/usr/bin/env python
"""
Launch a VM on Chameleon KVM@TACC using a flavor-based Blazar lease.
This version uses python-chi for reliable resource management.
"""

import os
# Set OS_CLOUD early to ensure all libraries pick it up
os.environ["OS_CLOUD"] = "chameleon"

import argparse
import socket
import subprocess
import sys
import time
import traceback
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import chi
import chi.server
import chi.lease
import openstack

TERMINAL_LEASE_STATES = {"ERROR", "FAILED", "TERMINATED", "DELETED"}
FLAVOR = "m1.medium"

def log(icon: str, msg: str) -> None:
    print(f"{icon}  {msg}", flush=True)

def die(msg: str) -> None:
    sys.exit(f"❌ {msg}")

class Tracker:
    def __init__(self):
        self.lease_id = None
        self.server = None
        self.fip = None
        self.created_keypair = None

def get_connection(cloud: str) -> openstack.connection.Connection:
    try:
        conn = openstack.connect(cloud=cloud)
        conn.authorize()
        return conn
    except Exception as exc:
        die(f"Failed to connect to cloud '{cloud}': {exc}")

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
    if img: return img
    images = list(conn.image.images())
    for fallback in ("CC-Ubuntu22.04", "CC-Ubuntu24.04", "CC-Ubuntu20.04"):
        match = next((i for i in images if i.name == fallback), None)
        if match:
            log("⚠️ ", f"Image '{identifier}' not found, using '{match.name}'")
            return match
    die(f"Image '{identifier}' not found.")

def find_network(conn, identifier: str):
    net = conn.network.find_network(identifier)
    if net: return net
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

def cleanup(conn, t: Tracker):
    log("", "Cleaning up resources...")
    if t.server:
        try: chi.server.delete_server(t.server.id)
        except: pass
    if t.fip:
        try: conn.network.delete_ip(t.fip, ignore_missing=True)
        except: pass
    if t.created_keypair:
        try: conn.compute.delete_keypair(t.created_keypair, ignore_missing=True)
        except: pass
    if t.lease_id:
        try: chi.lease.delete_lease(t.lease_id)
        except: pass

def parse_args():
    p = argparse.ArgumentParser(description="Launch a Chameleon KVM@TACC VM using python-chi.")
    p.add_argument("--cloud", default="chameleon")
    p.add_argument("--name", default="gregor-chameleon-vm")
    p.add_argument("--lease-name", default="kvm-flavor-lease")
    p.add_argument("--duration", type=float, default=1)
    p.add_argument("--count", type=int, default=1)
    p.add_argument("--lease-id", help="Existing ACTIVE lease")
    p.add_argument("--image", default="CC-Ubuntu22.04")
    p.add_argument("--flavor", default=FLAVOR)
    p.add_argument("--network", default="sharednet1")
    p.add_argument("--secgroup", default="default")
    p.add_argument("--keypair", default="chameleon-tmp-key")
    p.add_argument("--keyfile", default=str(Path.home() / ".ssh/id_rsa.pub"))
    p.add_argument("--privkey", default=str(Path.home() / ".ssh/id_rsa"))
    p.add_argument("--user", default="cc")
    p.add_argument("--command", default="uname -a")
    p.add_argument("--ext-net", default="public")
    p.add_argument("--wait", type=int, default=600)
    p.add_argument("--lease-timeout", type=int, default=600)
    p.add_argument("--ssh-timeout", type=int, default=180)
    p.add_argument("--cleanup", action="store_true")
    p.add_argument("--keep", action="store_true")
    return p.parse_args()

def main():
    args = parse_args()
    # Set environment variable to ensure python-chi uses the correct cloud config
    import os
    os.environ["OS_CLOUD"] = args.cloud

    args.name = f"{args.name}-{uuid.uuid4().hex[:8]}"
    t = Tracker()

    log("", f"Connecting to '{args.cloud}'...")
    conn = get_connection(args.cloud)

    # Set site for python-chi
    chi.use_site("KVM@TACC")

    # Monkey-patch chi.lease.blazar to use the working openstack session and real endpoint
    # This fixes the 'identity/token/id' None error by using a verified auth session
    from blazarclient.v1.client import Client
    try:
        # Resolve the real Blazar endpoint from the service catalog
        blazar_url = conn.catalog.get_endpoint('blazar', interface='public')
        log("✅", f"Resolved Blazar endpoint: {blazar_url}")

        def patched_blazar():
            return Client(
                blazar_url=blazar_url,
                session=conn.session
            )
        chi.lease.blazar = patched_blazar
    except Exception as e:
        log("⚠️ ", f"Could not resolve Blazar endpoint: {e}. Falling back to default chi auth.")

    ok = False
    try:
        # 1. Lease
        if args.lease_id:
            t.lease_id = args.lease_id
            log("✅", f"Using existing lease: {t.lease_id}")
        else:
            log("", f"Creating lease '{args.lease_name}'...")
            # Ensure flavor ID is resolved via SDK first
            flavor = conn.compute.find_flavor(args.flavor)
            t.lease_id = chi.lease.create_lease(args.lease_name, [{"resource_type": "flavor:instance", "flavor_id": flavor.id, "amount": args.count}])
            log("✅", f"Lease created: {t.lease_id}")

        # 2. Supporting resources
        keypair = ensure_keypair(conn, args.keypair, Path(args.keyfile), t)
        image = find_image(conn, args.image)
        network = find_network(conn, args.network)
        sg = ensure_ssh_rule(conn, args.secgroup)

        # 3. Boot and attach using python-chi
        log("", f"Booting '{args.name}' via python-chi...")
        t.server = chi.server.create_server(
            name=args.name,
            image_name=image.name,
            flavor_name=conn.compute.find_flavor(args.flavor).name,
            reservation_id=t.lease_id,
            key_name=keypair,
            secgroups=[sg.name],
            network_name=network.name,
            wait=True
        )
        log("✅", f"Server {t.server.id} is ACTIVE")

        # 4. Floating IP
        fip_addr = chi.server.associate_floating_ip(t.server.id)
        log("✅", f"Attached Floating IP: {fip_addr}")

        # We need the FIP object for cleanup
        t.fip = conn.network.find_ip(fip_addr)

        # 5. Verify
        user = "cc" if image.name.startswith("CC-") else args.user
        priv = Path(args.privkey)
        if not priv.is_file() and args.keyfile.endswith(".pub"):
            alt = Path(args.keyfile[:-4])
            priv = alt if alt.is_file() else priv

        ok = test_ssh(user, fip_addr, priv, args.command, args.ssh_timeout)

        print("\n" + "=" * 54)
        print("DEPLOYMENT COMPLETE" if ok else "DEPLOYED (SSH test did not pass)")
        print("=" * 54)
        print(f"  ssh -i {priv} {user}@{fip_addr}")

    except Exception as exc:
        log("❌", f"Failed: {exc}")
        traceback.print_exc()
        cleanup(conn, t)
        sys.exit(1)

    if args.cleanup:
        cleanup(conn, t)
    sys.exit(0 if ok else 2)

if __name__ == "__main__":
    main()
