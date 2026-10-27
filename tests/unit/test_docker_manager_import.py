def test_docker_manager_import():
    """DockerManager must import on supported Python versions."""
    from cloudmesh.ai.container.local.docker.DockerManager import DockerManager

    assert DockerManager is not None
