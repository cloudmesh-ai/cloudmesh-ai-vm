from fabric import Connection
from paramiko.client import AutoAddPolicy

from . import context


class Remote(Connection):
    """
    .. deprecated:: 1.0

    Wrapper for `Fabric Connection
    <https://docs.fabfile.org/en/latest/api/connection.html#fabric.connection.Connection>`__

    """

    def __init__(self, ip=None, server=None, user="cc", **kwargs):
        if ip is None:
            if server is None:
                raise ValueError("ip or server must be provided.")
            ip = server.ip

        if not kwargs.get("connect_kwargs"):
            kwargs["connect_kwargs"] = {}
        key_filename = context.get("keypair_private_key")
        kwargs["connect_kwargs"].setdefault("key_filename", key_filename)
        super(Remote, self).__init__(ip, user=user, **kwargs)
        # Default policy is to automatically add unknown hosts
        # - for our use-case, the host is almost always guaranteed to be unknown.
        self.client.set_missing_host_key_policy(AutoAddPolicy)
