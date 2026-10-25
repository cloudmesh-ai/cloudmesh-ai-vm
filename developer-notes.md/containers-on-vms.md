# Running Containers and Kubernetes on Cloud VMs

This chapter explores the intersection of Virtual Machines and Containerization. While many developers move directly to managed Kubernetes services, running containers on a cloud VM is often the best starting point for development, testing, and small-scale production.

## 1. The VM-Container Relationship

A common point of confusion is whether to use a VM or a Container. In professional environments, we often use **both**.

A VM provides the **Hardware Abstraction** (a dedicated kernel, isolated resources, and a strong security boundary). A container provides the **Application Abstraction** (packaged dependencies, fast startup, and environment consistency).

**The Workflow**: You provision a Cloud VM $\rightarrow$ Install a Container Runtime $\rightarrow$ Deploy your containers.

## 2. Container Runtimes on VMs

To run containers on a VM, you need a runtime.

### Docker: The Industry Standard
Docker is the most popular choice. It provides a complete ecosystem for building and running containers.
- **Installation**: Usually involves adding the Docker repository and installing the `docker-ce` engine.
- **Caveat**: By default, the Docker daemon runs as root, which can be a security risk.

### Podman: The Secure Alternative
Podman is a "daemonless" container engine.
- **Rootless Containers**: Podman allows you to run containers as a non-privileged user. If a container is compromised, the attacker does not automatically get root access to your VM.
- **Docker Compatibility**: Podman is designed to be a drop-in replacement for Docker (you can often just `alias docker=podman`).

## 3. The Networking Bridge: Port Mapping

When you run a container on a VM, the container has its own internal IP address. To make the application accessible to the world, you must create a "bridge" through two layers of firewalls.

### Layer 1: The Container $\rightarrow$ VM Mapping
You map a port on the VM to a port in the container.
```bash
# Map VM port 80 to Container port 8080
docker run -p 80:8080 my-web-app
```

### Layer 2: The VM $\rightarrow$ Cloud Firewall Mapping
Mapping the port in Docker is not enough. You must also go to your Cloud Console (or use the techniques in `firewalls.md`) to open the port in the Security Group.
- **Rule**: Allow TCP Port 80 from `0.0.0.0/0`.

## 4. Lightweight Kubernetes on VMs

If you need the orchestration power of Kubernetes (K8s) but don't want the cost/complexity of a managed service like EKS or GKE, you can run a "lightweight" cluster on your VM.

### K3s: The Lightweight Powerhouse
K3s is a highly optimized, single-binary version of Kubernetes. It is ideal for cloud VMs because it uses very little RAM.
- **Installation**: A single command:
  ```bash
  curl -sfL https://get.k3s.io | sh -
  ```
- **Use Case**: Running a production-ready, small-scale cluster on a single or few VMs.

### Kind (Kubernetes in Docker)
Kind allows you to run a Kubernetes cluster where the "nodes" are actually Docker containers.
- **Use Case**: Testing K8s manifests and Helm charts on a VM before deploying them to a real cluster.

## 5. Comparison: Where should my app live?

| Strategy | Setup Effort | Scaling | Isolation | Best For |
| :--- | :--- | :--- | :--- | :--- |
| **App on VM** | Low | Manual | High | Simple scripts, legacy apps |
| **Container on VM** | Medium | Easy | Medium | Microservices, CI/CD |
| **Managed K8s** | High | Automatic | High | Enterprise-scale, High Availability |

## Summary Checklist
- [ ] Install a container runtime (Docker or Podman).
- [ ] Set up a non-root user for container management.
- [ ] Map the container port to the VM port.
- [ ] Open the corresponding port in the Cloud Security Group.
- [ ] (Optional) Install K3s if you need orchestration (autoscaling, self-healing).