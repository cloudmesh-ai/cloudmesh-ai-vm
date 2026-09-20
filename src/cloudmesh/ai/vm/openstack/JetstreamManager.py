from cloudmesh.ai.vm.openstack.OpenstackManager import OpenstackManager

class Provider(OpenstackManager):
    """
    Jetstream implementation of the OpenstackManager.
    """

    def __init__(self, config, **kwargs):
        super().__init__(config, cloud_name="jetstream", **kwargs)

    def get_cost(self, **kwargs) -> Optional[Any]:
        """
        Calculates and returns the cost (in SUs) for Jetstream based on usage patterns.
        """
        # Dictionary mapping instance flavors to their hourly SU cost
        # Source: https://docs.jetstream-cloud.org/general/instance-flavors/
        su_costs = {
            "m3.tiny": 1,
            "m3.small": 2,
            "m3.quad": 4,
            "m3.medium": 8,
            "m3.large": 16,
            "m3.xl": 32,
            "m3.2xl": 64,
            "m3.3xl": 128,
            "r3.large": 128,
            "r3.xl": 256,
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

        cloud_config = self.get_cloud_config(self.cloud_name)
        
        flavor = kwargs.get("flavor") or cloud_config.get("flavor") or "m3.medium"
        num_instances = kwargs.get("num_instances") or cloud_config.get("num_instances", 1)
        hours_per_day = kwargs.get("hours_per_day") or cloud_config.get("hours_per_day", 8)
        days_per_week = kwargs.get("days_per_week") or cloud_config.get("days_per_week", 5)
        weeks = kwargs.get("weeks") or cloud_config.get("weeks", 52)

        if flavor not in su_costs:
            return {"value": "Unknown", "unit": "SU", "details": f"Error: Unknown instance flavor: {flavor}"}

        hourly_cost = su_costs[flavor]
        total_sus = (
            hourly_cost
            * hours_per_day
            * days_per_week
            * weeks
            * num_instances
        )

        details = (
            f"Jetstream Service Unit (SU) Estimation:\n"
            f"- Flavor: {flavor} ({hourly_cost} SU/hour)\n"
            f"- Usage: {num_instances} instance(s), {hours_per_day} hours/day, "
            f"{days_per_week} days/week, {weeks} weeks"
        )

        return {
            "value": total_sus,
            "unit": "SU",
            "details": details
        }
