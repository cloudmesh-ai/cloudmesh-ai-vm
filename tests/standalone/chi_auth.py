import os
import openstack
import logging
from unittest.mock import patch

def authenticate_chi_from_cloud(cloud_name: str):
    """
    Forces the chi library to use credentials from clouds.yaml by monkey-patching
    the keystoneauth1 loading mechanism.
    """
    try:
        # 1. Load the cloud configuration using OpenStack SDK
        conn = openstack.connect(cloud=cloud_name)
        sdk_auth = conn.session.auth

        # 2. Extract the actual auth object (ApplicationCredential or Token)
        # We want the underlying keystoneauth1 auth plugin
        chi_auth_plugin = sdk_auth

        # 3. Monkey-patch 'keystoneauth1.loading.load_auth_from_conf_options'
        # This is the function chi calls to decide how to authenticate.
        # We force it to return our SDK-loaded auth plugin regardless of config.

        import keystoneauth1.loading

        # We use a lambda to ensure the return value is always our loaded auth
        keystoneauth1.loading.load_auth_from_conf_options = lambda conf, group: chi_auth_plugin

        # 4. Also inject environment variables as a fallback for other tools
        env_map = {
            'OS_AUTH_URL': getattr(chi_auth_plugin, 'auth_url', None),
            'OS_PROJECT_NAME': getattr(chi_auth_plugin, 'project_name', None),
            'OS_PROJECT_DOMAIN_NAME': getattr(chi_auth_plugin, 'project_domain_name', None),
        }

        if hasattr(chi_auth_plugin, 'auth_methods') and chi_auth_plugin.auth_methods:
            method = chi_auth_plugin.auth_methods[0]
            env_map['OS_AUTH_TYPE'] = 'application_credential'
            env_map['OS_APPLICATION_CREDENTIAL_ID'] = getattr(method, 'application_credential_id', None)
            env_map['OS_APPLICATION_CREDENTIAL_SECRET'] = getattr(method, 'application_credential_secret', None)
        elif getattr(chi_auth_plugin, 'token', None):
            env_map['OS_AUTH_TYPE'] = 'v3token'
            env_map['OS_TOKEN'] = chi_auth_plugin.token

        for var, val in env_map.items():
            if val:
                os.environ[var] = val

        print(f"Successfully monkey-patched chi to use cloud '{cloud_name}' credentials.")

    except Exception as e:
        logging.error(f"Failed to authenticate using cloud '{cloud_name}': {e}")
        raise RuntimeError(f"Could not load credentials from clouds.yaml for cloud '{cloud_name}'") from e
