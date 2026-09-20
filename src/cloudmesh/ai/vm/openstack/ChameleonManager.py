import yaml
from cloudmesh.ai.vm.openstack.OpenstackManager import OpenstackManager

try:
    import chi
except ImportError:
    # Mocking chi for environments where it is not installed
    class ChiMock:
        def use_site(self, site): pass
        def set(self, key, value): pass
        class Lease:
            def add_node_reservation(self, res, node_type, count): res.append({"node_type": node_type, "count": count})
            def lease_duration(self, days): return "start", "end"
            def create_lease(self, name, res, start_date, end_date): pass
        lease = Lease()
    chi = ChiMock()

class Provider(OpenstackManager):
    """
    Chameleon Cloud implementation of the OpenstackManager.
    """

    def __init__(self, config, **kwargs):
        super().__init__(config, cloud_name="chameleon", **kwargs)

    def list_regions(self) -> List[Dict[str, Any]]:
        """Lists available sites/regions in Chameleon Cloud."""
        try:
            sites_dict = chi.context.list_sites(show=None)
            regions = []
            for site_name, properties in sites_dict.items():
                regions.append({"name": site_name, **properties})
            return regions
        except Exception as e:
            self.print(f"Error listing Chameleon regions: {e}")
            return []

    def create_reservation(self, name: str, node_type: str, count: int, start_date: str = None, end_date: str = None, duration: int = None) -> bool:
        """
        Creates a node reservation (lease) in Chameleon Cloud using python-chi.
        """
        cloud_config = self.get_cloud_config("chameleon")
        site = cloud_config.get("site", "CHI@TACC")
        project = cloud_config.get("project_name")

        if not project:
            self.print("Error: 'project_name' must be configured in clouds.yaml for Chameleon reservations.")
            return False

        try:
            # Configure chi
            chi.use_site(site)
            chi.set("project_name", project)

            reservations = []
            chi.lease.add_node_reservation(
                reservations,
                node_type=node_type,
                count=count,
            )

            # Determine start and end dates
            if duration:
                s, e = chi.lease.lease_duration(days=duration)
            elif start_date and end_date:
                s, e = start_date, end_date
            else:
                s, e = chi.lease.lease_duration(days=1)

            chi.lease.create_lease(
                name,
                reservations,
                start_date=s,
                end_date=e,
            )
            return True
        except Exception as e:
            self.print(f"Error creating reservation in Chameleon: {e}")
            return False

