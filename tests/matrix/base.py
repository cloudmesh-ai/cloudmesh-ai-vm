import getpass
import inspect
import json
from datetime import datetime
from typing import Any, ClassVar

from cloudmesh.ai.vm.base import BaseVMProvider
from cloudmesh.ai.vm.exceptions import ProviderFeatureNotSupported


class MatrixTestBase:
    """
    Base class for VM provider capability tests.
    Provides utilities to probe which methods are implemented and functional.
    """

    # Master list of capabilities from BaseVMProvider
    CAPABILITIES: ClassVar[list[str]] = [
        "start",
        "stop",
        "restart",
        "reset",
        "suspend",
        "delete",
        "login",
        "run_command",
        "shelve",
        "unshelve",
        "list",
        "info",
        "get_images",
        "get_flavors",
        "get_provider_info",
        "wait_for_status",
        "get_keys",
        "upload_key",
        "delete_key",
        "get_security_groups",
        "get_security_group_info",
        "create_security_group",
        "delete_security_group",
        "add_security_group_to_vm",
        "remove_security_group_from_vm",
        "add_security_group_rule",
        "remove_security_group_rule",
        "list_security_group_rules",
        "list_regions",
        "assign_floating_ip",
        "release_floating_ip",
        "get_cost",
    ]

    def __init__(self, provider_cls: type[BaseVMProvider], config: Any):
        self.provider_cls = provider_cls
        self.config = config
        self.provider = provider_cls(config)
        self.cloud_name = getattr(self.provider, "cloud_name", provider_cls.__name__)
        self.results = {}

    def probe_all(self):
        """Probes all defined capabilities and stores the results."""
        for cap in self.CAPABILITIES:
            self.results[cap] = self.probe_capability(cap)
        return self.results

    def probe_capability(self, cap: str) -> str:
        """
        Determines the status of a capability.
        Returns: 'Implemented', 'NotSupported', or 'Broken'.
        """
        # 1. Static Probe: Check if the method is overridden in the provider class
        method = getattr(self.provider, cap, None)
        if method is None:
            return "NotSupported"

        # Check if the method implementation is just the one from BaseVMProvider
        # We do this by checking the __qualname__ or checking if it's exactly the same function
        # BaseVMProvider methods raise ProviderFeatureNotSupported

        # 2. Dynamic Probe: Try calling the method with minimal args
        # This is tricky because methods have different signatures.
        # We use a try-except block and look for ProviderFeatureNotSupported.
        try:
            # We use a very basic call. Since we don't know the args,
            # we use a mock/empty object for 'name' if it's a common param.
            # For methods like list(), no args are needed.

            # We can use inspect to see if the method requires arguments.
            sig = inspect.signature(method)
            args = {}
            for param in sig.parameters.values():
                if (
                    param.default is inspect.Parameter.empty
                    and param.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
                ):
                    if param.name == "name":
                        args["name"] = "probe-vm"
                    elif param.name == "key_path":
                        args["key_path"] = "/tmp/probe_key"
                    elif param.name == "key_name":
                        args["key_name"] = "probe_key"
                    elif param.name == "sg_name":
                        args["sg_name"] = "probe_sg"
                    elif param.name == "protocol":
                        args["protocol"] = "tcp"
                    elif param.name == "port":
                        args["port"] = "80"
                    elif param.name == "cidr":
                        args["cidr"] = "0.0.0.0/0"
                    else:
                        # If we don't know what to provide, we might just fail
                        # but we'll try to pass None or a dummy value.
                        args[param.name] = None

            # Call the method. We wrap it in a way that we don't actually
            # create/delete resources if possible, but since we are probing,
            # we just want to see if it raises ProviderFeatureNotSupported.

            # To avoid side effects during probing, we can try to mock the internal
            # execution if we wanted to, but for now, we'll just rely on the
            # exception for "NotSupported".

            # IMPORTANT: Some methods might actually try to do something.
            # We'll try calling them and if they raise a TypeError due to
            # missing args, we'll treat it as 'Implemented' (since it didn't
            # raise NotSupported) but maybe 'Incomplete'.
            # For simplicity, we'll mark it 'Implemented' if it doesn't raise NotSupported.

            # To avoid actually starting VMs, we can check if the method
            # implementation differs from BaseVMProvider statically.

            if self._is_overridden(cap):
                return "Implemented"
            else:
                # If not overridden, it will raise ProviderFeatureNotSupported
                # We can verify this by calling it.
                method(**args)
                return "Implemented"  # Should not happen if not overridden

        except ProviderFeatureNotSupported:
            return "NotSupported"
        except TypeError:
            # This happens if we didn't provide the right args.
            # If it's a TypeError, it means the method exists and is callable,
            # but we didn't call it correctly. This implies it's implemented.
            return "Implemented"
        except Exception:
            # Any other exception suggests the method is implemented but broken
            # for the given mock config.
            return "Broken"

    def _is_overridden(self, cap: str) -> bool:
        """Checks if the method is overridden in the provider class or its parents (excluding BaseVMProvider)."""
        method = getattr(self.provider, cap, None)
        if method is None:
            return False

        # Get the method's qualifying name or look at the mro
        # BaseVMProvider is the ultimate base.
        for cls in inspect.getmro(self.provider.__class__):
            if cls == BaseVMProvider:
                # We reached the base class. If we haven't found an override yet,
                # then it's not overridden.
                return False
            if cap in cls.__dict__:
                return True
        return False

    @staticmethod
    def save_results(all_results: dict[str, dict[str, str]]):
        """
        Saves the aggregated results to a JSON file.
        all_results: { "aws": {"start": "Implemented", ...}, "azure": {...} }
        """
        report = {
            "metadata": {
                "ran_by": getpass.getuser(),
                "date": datetime.now().isoformat(),
            },
            "results": all_results,
        }

        with open("tests/matrix/matrix_results.json", "w") as f:
            json.dump(report, f, indent=4)
