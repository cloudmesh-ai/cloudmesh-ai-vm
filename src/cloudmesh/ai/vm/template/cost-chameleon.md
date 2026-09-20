# Chameleon Cloud Cost and Allocation Guide

> ⚠️ **Warning**
> The official document to the Chameleon Cost guide is locakted at this
> [link](https://chameleoncloud.org/learn/frequently-asked-questions/#toc-what-are-the-units-of-an-allocation-and-how-am-i-charged-).
> As charge rates can change you are encouraged to double check the
> current rates, The document below may not be up to date. It was
> created from a document dating from 09.10.2026

## What are the units of an allocation, and how am I charged?

Chameleon allocations can consist of several components of the system. Users can request allocation of individual compute nodes, storage servers, or specialized hardware such as GPUs and FPGAs.

Resources are allocated and charged in Service Units (SUs) which equate to one hour of wall clock time on a base bare metal server.

**Base Bare Metal Servers**: One SU equates to one hour of wall clock time on a base bare metal server (i.e., no attachments). Note this unit differs from traditional HPC or cloud service units that are charged in core-hours; a Chameleon SU is a full server, as the type of experiments and performance measurements users may wish to do may be contaminated by sharing nodes. Specific instances may be charged a multiple of an SU (e.g., if they include accelerators or other special features, see below).

**Specialized Bare Metal Hardware**: Servers with expensive and unique features including storage, GPU, or FPGA nodes are charged at 2x the rate of standard compute servers (i.e., 1 hour of use on 1 storage server costs 2 SUs).

**A100 Bare Metal Hardware**: Servers with our most modern GPUs are charged at 4x the rate of standard compute servers (i.e., 1 hour of use on 1 A100 bare metal server costs 4 SUs). This rate is constant for hosts with more than 1 GPU. For example, hosts that contain 4x A100 GPUs are charged an hourly rate of 16 SUs.

**Reservable Network Resources**: Reserved floating IP addresses and non-stitchable VLANs are both charged at a rate of 1 SU per hour. Reserved stitchable VLANs are charged at a rate of 2 SUs per hour.

**Virtual Machines (KVM Instances)**: KVM instances also require a reservation and are charged based on the fraction of the host server's resources they use.

### Summary of Charge Rates

| Resource Type | Charge Rate (per hour) | Maximum Duration |
|---|---|---|
| Base Bare Metal Server | 1 SU | 7 days |
| Specialized Bare Metal Server: FPGAs, Storage Nodes, High RAM, All GPUs except A100 | 2 SUs | 7 days |
| Bare Metal A100 GPU | 4 SUs | 7 days |
| 4x Bare Metal A100 GPU | 16 SUs | 7 days |
| Reservable Floating IP/Non-Stitchable VLAN | 1 SU | 7 days |
| Reservable Stitchable VLAN | 2 SUs | 7 days |
| KVM Instance | Fractional (See details below) | Up to 6 months |

The basic principle for charging SUs is to evaluate the amount of time a fraction of the resource is unavailable to other users. If you make a reservation, you will be charged for the reserved time whether you use the resources or not, as they are held for you. You may cancel a reservation at any time before it starts to avoid being charged.

## How are KVM instances (virtual machines) charged?

All KVM instances require a reservation and are charged against your project’s SU allocation.

The core principle is that a KVM instance is charged based on the fraction of the physical host's resources it consumes. The charge is calculated based on the fraction of CPU cores the VM uses relative to the total available on the host (typically 48 cores). The same principle applies to specialized resources like GPUs. We then round these fractional prices down to account for hypervisor and Noisy Neighbors overhead.

For example, a bare metal host with 4x modern GPUs (e.g., 4x A100s or H100s) has a charge rate of 16 SUs per hour. The g1.h100.pci.1 flavor reserves 1 of 4 available H100 GPUs, so your project will be charged for 1/4 of the host's rate (16 SUs), which is 4 SUs per hour.

Storage for KVM instances is not charged against your SU allocation.

### KVM Instance Flavors and SU Costs

| Flavor Name | vCPUs | RAM (MB) | SU Cost / Hour | Maximum Duration |
|---|---|---|---|---|
| m1.tiny | 1 | 512 | 0.01 | 6 months |
| m1.small | 1 | 2048 | 0.02 | 6 months |
| m1.medium | 2 | 4096 | 0.04 | 6 months |
| m1.large | 4 | 8192 | 0.08 | 6 months |
| m1.xlarge | 8 | 16384 | 0.15 | 6 months |
| m1.xxlarge | 16 | 32768 | 0.3 | 6 months |
| g1.h100.pci.1 | 24 | 49152 | 4 | 7 days |
| g1.h100.pci.4 | 192 | 1000000 | 16 | 7 days |

Note: SU Costs for standard flavors are calculated based on a 48-core host. You cannot currently reserve a VM with FPGA resources.


## Cost Estimation

You can get a dynamic cost estimate for your usage using the following command:

```bash
cmc vm cost
```

You can also override the default parameters to see how different configurations affect the cost:

```bash
cmc vm cost --flavor <flavor> --num_instances <number> --hours_per_day <hours> --days_per_week <days> --weeks <weeks>
```
