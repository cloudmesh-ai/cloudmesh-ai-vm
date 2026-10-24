import sys

from chi import lease

from cloudmesh.ai.vm.providers import get_provider

# 1. Use the provider system to handle authentication and site selection
# This ensures we use the same authentication as 'cmx vm list'
try:
    provider = get_provider("chameleon")
    provider._setup_chi_context()
except Exception as e:
    print(f"Error initializing Chameleon provider: {e}")
    sys.exit(1)


def inspect_reservation_details(reservation_id):
    """Searches through project leases to find a specific reservation ID

    and prints its detailed properties along with its parent lease info.
    """
    print(f"Searching for reservation ID: {reservation_id} across project leases...")

    try:
        leases = lease.list_leases()
    except Exception as e:
        print(f"Error fetching leases from Chameleon: {e}")
        return

    target_lease = None
    target_reservation = None

    # Check all possible reservation types in each lease
    res_types = [
        "flavor_reservations",
        "node_reservations",
        "fip_reservations",
        "network_reservations",
        "device_reservations",
    ]

    for l in leases:
        for res_type in res_types:
            reservations = getattr(l, res_type, [])
            for res in reservations:
                res_id = (
                    res.get("id") if isinstance(res, dict) else getattr(res, "id", None)
                )
                if res_id == reservation_id:
                    target_lease = l
                    target_reservation = res
                    break
            if target_reservation:
                break
        if target_reservation:
            break

    if not target_reservation:
        print(
            f"\n❌ Reservation ID '{reservation_id}' was not found in any active or"
            " accessible leases for this project."
        )
        return

    def get_val(obj, key, default="N/A"):
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    res_id = get_val(target_reservation, "id")
    res_type = get_val(target_reservation, "resource_type")
    min_count = get_val(target_reservation, "min")
    max_count = get_val(target_reservation, "max")
    resource_properties = get_val(target_reservation, "resource_properties", {})
    res_status = get_val(target_reservation, "status", "Active")

    lease_id = get_val(target_lease, "id")
    lease_name = get_val(target_lease, "name")
    lease_status = get_val(target_lease, "status")
    start_date = get_val(target_lease, "start_date")
    end_date = get_val(target_lease, "end_date")

    print("\n" + "=" * 65)
    print(" CHAMELEON RESERVATION INSPECTION")
    print("=" * 65)
    print(f"  Reservation ID   : {res_id}")
    print(f"  Resource Type    : {res_type}")
    print(f"  Count (Min-Max)  : {min_count} - {max_count}")
    print(f"  Status           : {res_status}")
    print(f"  Resource Props   : {resource_properties}")
    print("-" * 65)
    print(" PARENT LEASE CONTEXT:")
    print(f"  Lease Name       : {lease_name}")
    print(f"  Lease ID         : {lease_id}")
    print(f"  Lease Status     : {lease_status}")
    print(f"  Start Time       : {start_date}")
    print(f"  End Time         : {end_date}")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    target_res_id = "2aabdb15-1081-405c-a7b4-5f2e3d4df85d"
    inspect_reservation_details(target_res_id)
