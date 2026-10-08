#!/usr/bin/env python3

import argparse
import socket
import sys
from urllib.parse import urlparse

import openstack
import requests


def parse_args():
    parser = argparse.ArgumentParser(
        description="Probe and test reachability of all registered OpenStack services for a cloud."
    )
    parser.add_argument(
        "--cloud",
        default="jetstream",
        help="Cloud name from clouds.yaml (default: jetstream)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=3.0,
        help="Timeout in seconds for probing each endpoint (default: 3.0)",
    )
    return parser.parse_args()


def check_tcp_port(host: str, port: int, timeout: float = 3.0) -> bool:
    """Test raw TCP connectivity to host:port."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def probe_endpoint(url: str, timeout: float = 3.0) -> dict:
    """Probe an endpoint URL for TCP reachability and HTTP response status."""
    parsed = urlparse(url)
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)

    # 1. First test raw TCP connectivity
    tcp_ok = check_tcp_port(host, port, timeout=timeout)
    if not tcp_ok:
        return {
            "status": "TCP_REFUSED",
            "message": f"Connection refused / unreachable on {host}:{port}",
            "ok": False,
        }

    # 2. Test HTTP response
    try:
        resp = requests.get(url, timeout=timeout, verify=False)
        return {
            "status": f"HTTP {resp.status_code}",
            "message": f"Responded with HTTP {resp.status_code}",
            "ok": True,
        }
    except requests.exceptions.SSLError:
        return {
            "status": "SSL_ERROR",
            "message": "TCP open, but SSL verification failed",
            "ok": True,
        }
    except requests.exceptions.RequestException as exc:
        return {
            "status": "HTTP_ERROR",
            "message": f"TCP open, HTTP request failed ({exc.__class__.__name__})",
            "ok": False,
        }


def main():
    args = parse_args()
    print(f"🔍 Connecting to OpenStack cloud '{args.cloud}'...")

    try:
        conn = openstack.connect(cloud=args.cloud)
        conn.authorize()
    except Exception as exc:
        sys.exit(f"❌ Failed to connect to cloud '{args.cloud}': {exc}")

    # Suppress insecure SSL warnings for probing
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    session = conn.session
    access_data = session.auth.get_access(session)
    catalog = access_data.service_catalog.catalog

    if not catalog:
        sys.exit(f"❌ No service catalog returned for cloud '{args.cloud}'.")

    print(f"📋 Found {len(catalog)} services in the Keystone catalog for '{args.cloud}'. Probing endpoints...\n")

    results = []

    for entry in sorted(catalog, key=lambda x: x.get("type", "")):
        srv_type = entry.get("type", "unknown")
        srv_name = entry.get("name", "unknown")

        public_eps = [
            ep.get("url")
            for ep in entry.get("endpoints", [])
            if ep.get("interface") == "public"
        ]
        endpoint_url = public_eps[0] if public_eps else None

        if not endpoint_url:
            all_eps = [ep.get("url") for ep in entry.get("endpoints", [])]
            endpoint_url = all_eps[0] if all_eps else "N/A"

        if endpoint_url == "N/A":
            probe = {"status": "NO_ENDPOINT", "message": "No endpoint URL defined", "ok": False}
        else:
            probe = probe_endpoint(endpoint_url, timeout=args.timeout)

        results.append({
            "type": srv_type,
            "name": srv_name,
            "url": endpoint_url,
            "probe": probe,
        })

    # Print summary table
    col_type = 20
    col_name = 14
    col_status = 18
    col_url = 52

    header = f"{'Service Type':<{col_type}} {'Name':<{col_name}} {'Status':<{col_status}} {'Endpoint URL'}"
    separator = "-" * (col_type + col_name + col_status + col_url)

    print(header)
    print(separator)

    for item in results:
        probe = item["probe"]
        icon = "✅" if probe["ok"] else "❌"
        status_text = f"{icon} {probe['status']}"
        print(f"{item['type']:<{col_type}} {item['name']:<{col_name}} {status_text:<{col_status}} {item['url']}")

    print(separator)

    # Highlight Heat / Orchestration specifically
    heat_item = next((r for r in results if "orchestrat" in r["type"] or "heat" in r["name"]), None)
    if heat_item:
        print("\n🔥 Heat Orchestration Status:")
        if heat_item["probe"]["ok"]:
            print(f"   ✅ Heat is ACTIVE and responding at {heat_item['url']}.")
        else:
            print(f"   ❌ Heat is REGISTERED in Keystone, but the endpoint is NOT RESPONDING.")
            print(f"      Detail: {heat_item['probe']['message']}")
            print(f"      Conclusion: Heat is disabled / down on '{args.cloud}'.")
    else:
        print(f"\n🔥 Heat Orchestration is NOT registered in the service catalog for '{args.cloud}'.")


if __name__ == "__main__":
    main()
