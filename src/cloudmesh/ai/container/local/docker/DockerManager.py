import docker
import builtins
from typing import Any
from cloudmesh.ai.vm.CloudBaseManager import CloudBaseManager
from cloudmesh.ai.vm.exceptions import ProviderFeatureNotSupported
from cloudmesh.ai.vm.logger import logger

class DockerManager(CloudBaseManager):
    """
    Manages Docker containers using the docker-py library.
    """

    def __init__(self, config: Any, cloud_name: str = "docker", console=None, **kwargs):
        super().__init__(config, console=console, **kwargs)
        self.cloud_name = cloud_name
        try:
            self.client = docker.from_env()
            logger.debug("Docker client initialized from environment.")
        except Exception as e:
            logger.error(f"Failed to initialize Docker client: {e}")
            self.client = None

    def list(self) -> builtins.list[dict[str, Any]]:
        """Lists all Docker containers (running and stopped)."""
        if not self.client:
            return []
        
        containers = self.client.containers.list(all=True)
        return [
            {
                "name": c.name,
                "id": c.id[:12],
                "status": c.status,
                "image": c.image.tags[0] if c.image.tags else "none",
            }
            for c in containers
        ]

    def start(self, name: str | None = None, flavor: str | None = None, image: str | None = None, dockerfile: str | None = None, network: str | None = None, cmd: str | None = None, **kwargs) -> str:
        """Starts a container. If it doesn't exist, creates one. If dockerfile is provided, builds image first."""
        if not self.client:
            raise Exception("Docker client not available")

        name = name or "docker-container"
        
        if self.exists(name):
            container = self.client.containers.get(name)
            container.start()
            return f"Container {name} started."
        
        # Handle Dockerfile build
        if dockerfile:
            try:
                logger.info(f"Building image from Dockerfile: {dockerfile}")
                # build returns a tuple (Image, logs)
                image_obj, build_logs = self.client.images.build(path=dockerfile)
                image = image_obj.tags[0] if image_obj.tags else "built-image"
            except Exception as e:
                raise Exception(f"Failed to build image from Dockerfile {dockerfile}: {e}")
        else:
            image = image or "ubuntu:latest"

        container = self.client.containers.run(
            image, 
            command=cmd,
            name=name, 
            detach=True, 
            network=network
        )
        return f"Container {name} created and started from image {image}."

    def stop(self, name: str | None = None) -> bool:
        """Stops a Docker container."""
        if not self.client or not name:
            return False
        try:
            container = self.client.containers.get(name)
            container.stop()
            return True
        except Exception as e:
            logger.error(f"Error stopping container {name}: {e}")
            return False

    def restart(self, name: str | None = None) -> bool:
        """Restarts a Docker container."""
        if not self.client or not name:
            return False
        try:
            container = self.client.containers.get(name)
            container.restart()
            return True
        except Exception as e:
            logger.error(f"Error restarting container {name}: {e}")
            return False

    def delete(self, name: str | None = None) -> bool:
        """Deletes a Docker container."""
        try:
            container = self.client.containers.get(name)
            container.remove(force=True)
            return True
        except Exception as e:
            logger.error(f"Error deleting container {name}: {e}")
            return False

    def info(self, name: str, kind: str = "vm") -> dict[str, Any]:
        """Gets detailed info for a Docker container."""
        if not self.client:
            return {}
        try:
            container = self.client.containers.get(name)
            attrs = container.attrs
            return {
                "name": attrs['Name'],
                "id": attrs['Id'],
                "status": attrs['State']['Status'],
                "image": attrs['Config']['Image'],
                "ip": attrs['NetworkSettings']['IPAddress'] or \
                    next(iter(attrs['NetworkSettings']['Networks'].values()), {}).get('IPAddress', 'N/A'),
            }
        except Exception as e:
            logger.error(f"Error getting info for container {name}: {e}")
            return {}

    def login(self, name: str | None = None) -> bool:
        """Executes a shell in the container."""
        if not self.client or not name:
            return False
        
        import subprocess
        try:
            # Use docker exec -it to provide a shell
            subprocess.run(["docker", "exec", "-it", name, "/bin/bash"], check=True)
            return True
        except Exception as e:
            logger.error(f"Error logging into container {name}: {e}")
            return False

    def run_command(self, name: str, cmd: str) -> str:
        """Runs a command in the container and returns output."""
        if not self.client:
            return "Docker client not available"
        try:
            container = self.client.containers.get(name)
            result = container.exec_run(cmd)
            return result.output.decode('utf-8')
        except Exception as e:
            return f"Error running command: {e}"

    def pause(self, name: str) -> bool:
        """Pauses a Docker container."""
        if not self.client or not name:
            return False
        try:
            container = self.client.containers.get(name)
            container.pause()
            return True
        except Exception as e:
            logger.error(f"Error pausing container {name}: {e}")
            return False

    def unpause(self, name: str) -> bool:
        """Unpauses a Docker container."""
        if not self.client or not name:
            return False
        try:
            container = self.client.containers.get(name)
            container.unpause()
            return True
        except Exception as e:
            logger.error(f"Error unpausing container {name}: {e}")
            return False

    def list_images(self) -> list[dict[str, Any]]:
        """Lists Docker images."""
        if not self.client:
            return []
        try:
            images = self.client.images.list()
            return [{"id": img.id, "tags": img.tags} for img in images]
        except Exception as e:
            logger.error(f"Error listing images: {e}")
            return []

    def pull_image(self, image: str) -> bool:
        """Pulls a Docker image."""
        if not self.client:
            return False
        try:
            self.client.images.pull(image)
            return True
        except Exception as e:
            logger.error(f"Error pulling image {image}: {e}")
            return False

    def delete_image(self, image_id: str) -> bool:
        """Deletes a Docker image."""
        if not self.client:
            return False
        try:
            self.client.images.remove(image=image_id)
            return True
        except Exception as e:
            logger.error(f"Error deleting image {image_id}: {e}")
            return False


    def delete_image(self, image_id: str) -> bool:
        """Deletes a Docker image."""
        if not self.client:
            return False
        try:
            self.client.images.remove(image=image_id)
            return True
        except Exception as e:
            logger.error(f"Error deleting image {image_id}: {e}")
            return False


    def get_container_ip(self, name: str) -> str | None:
        """Gets the IP address of a container."""
        if not self.client:
            return None
        try:
            container = self.client.containers.get(name)
            networks = container.attrs['NetworkSettings']['Networks']
            if networks:
                first_net = list(networks.values())[0]
                return first_net.get('IPAddress')
        except Exception as e:
            logger.error(f"Error getting IP for container {name}: {e}")
        return None

    def list_container_ips(self) -> list[dict[str, str]]:
        if not self.client:
            return []
        containers = self.client.containers.list()
        ips = []
        for c in containers:
            ip = self.get_container_ip(c.name)
            ips.append({"name": c.name, "ip": ip or "N/A"})

        return ips

    def create_network(self, name: str) -> bool:
        """Creates a Docker network."""
        if not self.client:
            return False
        try:
            self.client.networks.create(name, driver="bridge")
            return True
        except Exception as e:
            logger.error(f"Error creating network {name}: {e}")
            return False


    def list_networks(self) -> list[dict[str, Any]]:
        """Lists all Docker networks."""
        if not self.client:
            return []
        try:
            networks = self.client.networks.list()
            return [{"name": n.name, "id": n.id} for n in networks]
        except Exception as e:
            logger.error(f"Error listing networks: {e}")
            return []


    def delete_network(self, name: str) -> bool:
        if not self.client or not name:
            return False
        try:
            network = self.client.networks.get(name)
            network.remove()
            return True
        except Exception as e:
            return False

    def run_command(self, name: str, cmd: str) -> str:
        """Runs a command in the container and returns output."""
        if not self.client:
            return "Docker client not available"
        try:
            container = self.client.containers.get(name)
            result = container.exec_run(cmd)
            return result.output.decode('utf-8')
        except Exception as e:
            return f"Error running command: {e}"

            container.restart()
            return True
        except Exception as e:
            logger.error(f"Error restarting container {name}: {e}")
            return False

    def pause(self, name: str) -> bool:
        """Pauses a Docker container."""
        if not self.client or not name:
            return False
        try:
            container = self.client.containers.get(name)
            container.pause()
            return True
        except Exception as e:
            logger.error(f"Error pausing container {name}: {e}")
            return False

    def unpause(self, name: str) -> bool:
        """Unpauses a Docker container."""
        if not self.client or not name:
            return False
        try:
            container = self.client.containers.get(name)
            container.unpause()
            return True
        except Exception as e:
            logger.error(f"Error unpausing container {name}: {e}")
            return False

    def list_images(self) -> list[dict[str, Any]]:
        """Lists Docker images."""
        if not self.client:
            return []
        try:
            images = self.client.images.list()
            return [{"id": img.id, "tags": img.tags} for img in images]
        except Exception as e:
            logger.error(f"Error listing images: {e}")
            return []

    def pull_image(self, image: str) -> bool:
        """Pulls a Docker image."""
        if not self.client:
            return False
        try:
            self.client.images.pull(image)
            return True
        except Exception as e:
            logger.error(f"Error pulling image {image}: {e}")
            return False

    def delete_image(self, image_id: str) -> bool:
        """Deletes a Docker image."""
        if not self.client:
            return False
        try:
            self.client.images.remove(image=image_id)
            return True
        except Exception as e:
            logger.error(f"Error deleting image {image_id}: {e}")
            return False

    def get_container_ip(self, name: str) -> str | None:
        """Gets the IP address of a container."""
        if not self.client:
            return None
        try:
            container = self.client.containers.get(name)
            # IP is typically in the first network
            networks = container.attrs['NetworkSettings']['Networks']
            if networks:
                first_net = list(networks.values())[0]
                return first_net.get('IPAddress')
        except Exception as e:
            logger.error(f"Error getting IP for container {name}: {e}")
        return None

    def list_container_ips(self) -> list[dict[str, str]]:
        """Lists IPs for all running containers."""
        if not self.client:
            return []
        containers = self.client.containers.list()
        ips = []
        for c in containers:
            ip = self.get_container_ip(c.name)
            ips.append({"name": c.name, "ip": ip or "N/A"})
        return ips

        """Creates a Docker network."""
        if not self.client:
            return False
        try:
            self.client.networks.create(name, driver="bridge")
            return True
        except Exception as e:
            logger.error(f"Error creating network {name}: {e}")
            return False

    def list_networks(self) -> list[dict[str, Any]]:
        """Lists all Docker networks."""
        if not self.client:
            return []
        try:
            networks = self.client.networks.list()
            return [{"name": n.name, "id": n.id} for n in networks]
        except Exception as e:
            logger.error(f"Error listing networks: {e}")
            return []

    def delete_network(self, name: str) -> bool:
        """Deletes a Docker network."""
        if not self.client or not name:
            return False
        try:
            network = self.client.networks.get(name)
            network.remove()
            return True
        except Exception as e:
            logger.error(f"Error deleting network {name}: {e}")
            return False
