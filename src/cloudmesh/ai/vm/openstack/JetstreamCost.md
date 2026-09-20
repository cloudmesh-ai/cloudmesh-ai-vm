*  https://docs.jetstream-cloud.org/alloc/estimator/


* https://docs.jetstream-cloud.org/general/access/

# ACCESS Credits and Jetstream2

ACCESS allocations are measured in ACCESS credits. Those credits then may be [converted](https://allocations.access-ci.org/exchange_calculator){target=_blank} to resource-defined service units.

Jetstream2 allocations Jetstream core hours or service units (SUs).

!!! info "ACCESS to Jetstream2 SUs"

     For simplicity, we've aligned our SU value such that ***1 ACCESS Credit = 1 Jetstream2 SU***.</br>

SUs are consumed at a rate of:

*   Jetstream2 (CPU) - 1 SU per vCPU_core-hour (use of one virtual core of a CPU per hour).
*   Jetstream2-LM (Large Memory) - 2 SUs per vCPU_core-hour
*   Jetstream2-GPU - 2 SUs per vCPU_core-hour

Please refer to [VM Sizes and configurations](../general/vmsizes.md){target=_blank} to see available VM flavors and per hour cost on Jetstream2.

---

* **SUSPENDED** instances will be charged .75 of their normal SU value. (75%)
* **STOPPED** instances will be charge 0.50 of their normal SU value. (50%)
* **SHELVED** instances will not be charged SUs. (0%)

For Large Memory and GPU allocations, the vCPU core hour cost is 2x as noted above.

!!! question "Why do stopped and suspended instances still burn SUs?"

     The reason for continuing to charge for VMs that are not in a usable state is that they still consume resorces if they are suspended or stopped. In those states, they still occupy allocable/usable space on the hypervisor, preventing other users from using those resources.

***If your VM is active, even if you are not logged in and using it, it is still being charged for use. If you do not wish to be charged, shelve your instance***

!!! Note "Usage reporting"

     Usage reported to ACCESS is not in real time. There may be a delay of 12-24 hours for usage reporting.</br>


# Dictionary of Jetstream2 instance flavors mapped to their Service Unit (SU) cost per hour
JETSTREAM_FLAVORS = {
    # CPU Instances
    "m3.tiny": 1,
    "m3.small": 2,
    "m3.quad": 4,
    "m3.medium": 8,
    "m3.large": 16,
    "m3.xl": 32,
    "m3.2xl": 64,
    "m3.3xl": 128,
    
    # Large Memory Instances
    "r3.large": 128,
    "r3.xl": 256,
    
    # GPU Instances (Partial & Full)
    "g3.medium": 16,
    "g3.large": 32,
    "g3.xl": 64,
    "g4.xl": 84,
    "g4.2xl": 168,
    "g4.4xl": 336,
    "g5.xl": 128,
    "g5.2xl": 256,
    "g5.4xl": 512,
}

def calculate_jetstream_sus(flavor: str, num_instances: int, hours_per_day: float, 
                              days_per_week: float, total_weeks: float) -> float:
    """
    Calculates the total Service Units (SUs) required for a Jetstream2 allocation.
    
    Parameters:
    - flavor (str): The instance size/flavor (e.g., 'm3.medium', 'g4.xl')
    - num_instances (int): Number of instances used concurrently
    - hours_per_day (float): Active hours per day (1 to 24)
    - days_per_week (float): Active days per week (1 to 7)
    - total_weeks (float): Total duration in weeks (e.g., 52 for a full year)
    
    Returns:
    - float: Total estimated Service Units (SUs)
    """
    if flavor not in JETSTREAM_FLAVORS:
        raise ValueError(f"Unknown flavor '{flavor}'. Choose from: {list(JETSTREAM_FLAVORS.keys())}")
    
    su_per_hour = JETSTREAM_FLAVORS[flavor]
    
    # Total active hours calculation
    # Average active hours per week = hours_per_day * days_per_week
    total_hours = hours_per_day * days_per_week * total_weeks
    
    # Total SUs = (SU cost per hour) * (Total Hours) * (Number of Instances)
    total_sus = su_per_hour * total_hours * num_instances
    
    return total_sus


# --- Example Usage ---
if __name__ == "__main__":
    # Example 1: 2 'm3.medium' instances running 8 hours a day, 5 days a week, for 52 weeks
    sus_needed = calculate_jetstream_sus(
        flavor="m3.medium", 
        num_instances=2, 
        hours_per_day=8, 
        days_per_week=5, 
        total_weeks=52
    )
    print(f"Estimated SUs required: {sus_needed:,.2f}")

    # Example 2: Always-on 'm3.large' instance for a full year (24 hrs/day, 7 days/week, 52 weeks)
    always_on_sus = calculate_jetstream_sus(
        flavor="m3.large",
        num_instances=1,
        hours_per_day=24,
        days_per_week=7,
        total_weeks=52
    )
    print(f"Always-on m3.large SUs required: {always_on_sus:,.2f}")