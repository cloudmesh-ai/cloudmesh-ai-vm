# High Availability and Disaster Recovery for Cloud VMs

This chapter explains how to move from a single "fragile" virtual machine to a resilient architecture that can survive hardware failures, software crashes, and even entire data center outages.

## 1. The Single Point of Failure (SPOF)

A single VM, no matter how well-hardened or optimized, is a **Single Point of Failure**. If the physical host machine crashes, the hypervisor fails, or the underlying disk corrupts, your application goes offline.

The goal of **High Availability (HA)** is to eliminate SPOFs so that the system continues to function even when individual components fail.

## 2. Achieving High Availability

### Load Balancing
The most common way to achieve HA is to deploy multiple identical VMs and place them behind a **Load Balancer**.
- **Traffic Distribution**: The load balancer receives all incoming requests and distributes them across the VM pool (e.g., using Round Robin).
- **Redundancy**: If one VM crashes, the load balancer simply stops sending traffic to it, and the users never notice a disruption.

### Health Checks
A load balancer doesn't just blindly send traffic; it performs **Health Checks**.
- **The Ping/HTTP Check**: Every few seconds, the load balancer asks the VM, "Are you okay?" (e.g., by requesting `/health`).
- **Automatic Removal**: If the VM fails to respond or returns a 500 error, it is marked as "Unhealthy" and removed from the rotation until it recovers.

### Auto-Scaling Groups
To handle both failures and traffic spikes, cloud providers use **Auto-Scaling Groups**.
- **Self-Healing**: If a VM instance terminates unexpectedly, the group automatically launches a replacement from a Golden Image.
- **Dynamic Scaling**: If CPU usage across the group exceeds 70%, the group launches additional VMs to share the load.

## 3. Disaster Recovery (DR) Strategies

While HA protects you from a single VM failing, **Disaster Recovery** protects you from the data center failing.

### Multi-Zone Deployment (Availability Zones)
Cloud regions are divided into **Availability Zones (AZs)**—distinct physical data centers with independent power and cooling.
- **Strategy**: Deploy your VMs across at least two different AZs. If AZ-1 has a total power failure, your VMs in AZ-2 continue to run.

### Multi-Region Deployment
For mission-critical apps, you deploy across different geographic regions (e.g., US-East and US-West).
- **Strategy**: Use a Global Load Balancer to route users to the nearest healthy region. This protects against massive regional outages.

## 4. Defining Recovery Objectives

When designing for availability, you must define two key metrics:

- **RPO (Recovery Point Objective)**: "How much data can we afford to lose?" 
  - If your RPO is 1 hour, you must take snapshots/backups at least every hour.
- **RTO (Recovery Time Objective)**: "How long can we be offline?"
  - If your RTO is 5 minutes, you need an automated failover system (like a Load Balancer); manual restoration from backup would be too slow.

## 5. Availability Comparison Matrix

| Strategy | Cost | Complexity | Survives VM Crash? | Survives DC Outage? |
| :--- | :--- | :--- | :--- | :--- |
| **Single VM** | Low | Low | No | No |
| **HA Cluster (1 Zone)** | Medium | Medium | Yes | No |
| **Multi-Zone (AZ)** | Medium | Medium | Yes | Yes |
| **Multi-Region** | High | High | Yes | Yes |

## Summary Checklist
- [ ] Identify the Single Points of Failure in your current architecture.
- [ ] Deploy at least two instances of your application behind a load balancer.
- [ ] Configure health checks to ensure traffic only goes to healthy VMs.
- [ ] Spread your instances across at least two Availability Zones.
- [ ] Define your RPO and RTO and verify that your backup strategy meets them.