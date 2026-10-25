import docker
from typing import Any
from cloudmesh.ai.vm.CloudBaseManager import CloudBaseManager
from cloudmesh.ai.vm.exceptions import ProviderFeatureNotSupported
from cloudmesh.ai.vm.logger import logger

class DockerManager(CloudBaseManager):
    \"\"\"
    Manages Docker containers using the docker-py library.
    \"\"\"

    def __init__(self, config: Any, cloud_name: str = \"docker\", console=None, **kwargs):
        super().__init__(config, console=console, **kwargs)
        self.cloud_name = cloud_name
        try:
            self.client = docker.from_env()
            logger.debug(\"Docker client initialized from environment.\")
        except Exception as e:
            logger.error(f\"Failed to initialize Docker client: {e}\")
            self.client = None

    def list(self) -> list[dict[str, Any]]:
        \"\"\"Lists all Docker containers (running and stopped).\"\"\"
        if not self.client:
            return []
        
        containers = self.client.containers.list(all=True)
        return [
            {
                \"name\": c.name,
                \"id\": c.id[:12],
                \"status\": c.status,
                \"image\": c.image.tags[0] if c.image.tags else \"none\",
            }
            for c in containers
        ]

    def start(self, name: str | None = None, flavor: str | None = None, image: str | None = None, **kwargs) -> str:
        \"\"\"Starts a container. If it doesn't exist, creates one.\"\"\"
        if not self.client:
            raise Exception(\"Docker client not available\")

        name = name or \"docker-container\"
        
        if self.exists(name):
            container = self.client.containers.get(name)
            container.start()
            return f\"Container {name} started.\"
        
        # Create new container
        image = image or \"ubuntu:latest\"
        container = self.client.containers.run(
            image, 
            name=name, 
            detach=True, 
            # Basic mapping of 'flavor' to docker resources if provided
            # In a real implementation, flavor would be mapped to cpu/mem limits
        )
        return f\"Container {name} created and started from image {image}.\"

    def stop(self, name: str | None = None) -> bool:
        \"\"\"Stops a Docker container.\"\"\"
        if not self.client or not name:
            return False
        try:
            container = self.client.containers.get(name)
            container.stop()
            return True
        except Exception as e:
            logger.error(f\"Error stopping container {name}: {e}\")
            return False

    def restart(self, name: str | None = None) -> bool:
        \"\"\"Restarts a Docker container.\"\"\"
        if not self.client or not name:
            return False
        try:
            container = self.client.containers.get(name)
            container.restart()
            return True
        except Exception as e:
            logger.error(f\"Error restarting container {name}: {e}\")
            return False

    def delete(self, name: str | None = None) -> bool:
        \"\"\"Deletes a Docker container.\"\"\"
        if not self.client or not name:
            return False
        try:
            container = self.client.containers.get(name)
            container.remove(force=True)
            return True
        except Exception as e:
            logger.error(f\"Error deleting container {name}: {e}\")
            return False

    def info(self, name: str, kind: str = \"vm\") -> dict[str, Any]:
        \"\"\"Gets detailed info for a Docker container.\"\"\"
        if not self.client:
            return {}
        try:
            container = self.client.containers.get(name)
            attrs = container.attrs
            return {
                \"name\": attrs['Name'],
                \"id\": attrs['Id'],
                \"status\": attrs['State']['Status'],
                \"image\": attrs['Config']['Image'],
                \"ip\": attrs['NetworkSettings']['IPAddress'],
            }
        except Exception as e:
            logger.error(f\"Error getting info for container {name}: {e}\")
            return {}

    def login(self, name: str | None = None) -> bool:
        \"\"\"Executes a shell in the container.\"\"\"
        if not self.client or not name:
            return False
        
        import subprocess
        try:
            # Use docker exec -it to provide a shell
            subprocess.run([\"docker\", \"exec\", \"-it\", name, \"/bin/bash\"], check=True)
            return True
        except Exception as e:
            logger.error(f\"Error logging into container {name}: {e}\")
            return False

    def run_command(self, name: str, cmd: str) -> str:
        \"\"\"Runs a command in the container and returns output.\"\"\"
        if not self.client:
            return \"Docker client not available\"
        try:
            container = self.client.containers.get(name)
            result = container.exec_run(cmd)
            return result.output.decode('utf-8')
        except Exception as e:
            return f\"Error running command: {e}\"
