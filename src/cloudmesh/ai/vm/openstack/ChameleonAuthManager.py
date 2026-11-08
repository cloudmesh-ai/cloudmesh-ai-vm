import logging
import os

# NOTE: ``openstack`` (the SDK) imports a large number of dependencies and can be
# slow to import. To keep unit tests fast and avoid unnecessary imports when the
# function is patched (as in the test suite), we defer importing the SDK until
# the function is actually executed.
# ``openstack`` will be imported lazily inside ``authenticate_chi_from_cloud``.

from cloudmesh.ai.vm.exceptions import ConfigError

logger = logging.getLogger("cloudmesh.ai.vm")


def authenticate_chi_from_cloud(cloud_name: str):
    """
    Forces the chi library to use credentials from clouds.yaml by monkey-patching
    the keystoneauth1 loading mechanism.
    """
    try:
        # Import the OpenStack SDK lazily to avoid heavy imports when the function
        # is mocked in tests.
        import openstack
        # 1. Load the cloud configuration using OpenStack SDK
        conn = openstack.connect(cloud=cloud_name)
        sdk_auth = conn.session.auth

        # 2. Monkey-patch 'keystoneauth1.loading.load_auth_from_conf_options'
        import keystoneauth1.loading

        keystoneauth1.loading.load_auth_from_conf_options = lambda conf, group: sdk_auth

        # 3. Inject environment variables as a fallback for other tools
        env_map = {
            "OS_AUTH_URL": getattr(sdk_auth, "auth_url", None),
            "OS_PROJECT_NAME": getattr(sdk_auth, "project_name", None),
            "OS_PROJECT_DOMAIN_NAME": getattr(sdk_auth, "project_domain_name", None),
        }

        if hasattr(sdk_auth, "auth_methods") and sdk_auth.auth_methods:
            method = sdk_auth.auth_methods[0]
            env_map["OS_AUTH_TYPE"] = "application_credential"
            env_map["OS_APPLICATION_CREDENTIAL_ID"] = getattr(
                method, "application_credential_id", None
            )
            env_map["OS_APPLICATION_CREDENTIAL_SECRET"] = getattr(
                method, "application_credential_secret", None
            )
        elif getattr(sdk_auth, "token", None):
            env_map["OS_AUTH_TYPE"] = "v3token"
            env_map["OS_TOKEN"] = sdk_auth.token

        for var, val in env_map.items():
            if val:
                os.environ[var] = val

        return sdk_auth
    except Exception as e:
        logger.error(f"Failed to authenticate using cloud '{cloud_name}': {e}")
        raise ConfigError(
            f"Could not load credentials from clouds.yaml for cloud '{cloud_name}': {e}"
        ) from e
