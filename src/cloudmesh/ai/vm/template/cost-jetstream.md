## Cost on Jetstream

> ⚠️ **Warning**
> The official document to the Jetstream Cost guide is locakted at this
> [link](https://docs.jetstream-cloud.org/general/instance-flavors/). 
> As charge rates can change you are encouraged to double check the
> current rates, The document below may not be up to date. It was
> created from a document dating from 09.10.2026

## Instance Flavors

Jetstream2 provides a range of instance flavors (also known as sizes), each under three different types with different capabilities. These instances consume an allocation's service units (SUs) according to how much physical hardware they occupy. Larger instance flavors consume SUs at a greater rate.

The unit of allocation for Jetstream is based on a virtual CPU (vCPU) hour: *1 service unit (SU) is equivalent to 1 vCPU for 1 hour of wall clock time*. The tables below outline the instance types and flavors for Jetstream2.

> 💡 Note "Jetstream2 Resources"
> ***The three instance types are all separate ACCESS resources. When you exchange ACCESS credits, you must select Jetstream2 (CPU), Jetstream2 GPU, or Jetstream2 Large Memory in order to use each of them. Having access to one does NOT include access to all.***

While the root disk sizes are fixed for each instance flavor, there is an option called "volume-backed" that allows you to specify a larger root disk, using quota from your storage allocation. Instructions for this are in the user interface-specific documentation for creating an instance ([Exosphere](../ui/exo/create_instance.md/#configure-instance), [Horizon](../ui/horizon/launch.md/#launching-an-instance), [CLI](../ui/cli/launch.md/#creating-a-virtual-machine)).

## Jetstream2 CPU

| Flavor            | vCPUs | RAM (GB) | Local Storage (GB) | Cost per hour (SU) |
|:------------------|:-----:|:--------:|:------------------:|:------------------:|
| m3.tiny           |   1   |    3     |         20         |        1           |
| m3.small          |   2   |    6     |         20         |        2           |
| m3.quad           |   4   |    15    |         20         |        4           |
| m3.medium         |   8   |    30    |         60         |        8           |
| m3.large          |  16   |    60    |         60         |        16          |
| m3.xl             |  32   |   125    |         60         |        32          |
| m3.2xl            |  64   |   250    |         60         |        64          |
| m3.3xl[^largest]* |  128  |   500    |         60         |       128          |

\* *m3.3xl are not available by default. This flavor is available by submitting a request to [help@jetstream-cloud.org](mailto:help@jetstream-cloud.org) with proper justification.*

## Jetstream2 Large Memory

Jetstream2 Large Memory instances have double the memory (RAM) of equivalently-resourced CPU instances. They cost 2 SUs per vCPU hour, or 2 SUs per core per hour.

| Flavor             | vCPUs | RAM (GB) | Local Storage (GB) | Cost per hour (SU) |
|:-------------------|:-----:|:--------:|:------------------:|:------------------:|
| r3.large[^largest] |  64   |   500    |         60         |       128          |
| r3.xl[^largest]    |  128  |   1000   |         60         |       256          |

## Jetstream2 GPU

Jetstream2 GPU instances include a partial or full NVIDIA GPU, with up to 80 GB of GPU RAM.

### Partial GPU

Partial GPU instances offer access to a portion of an A100 GPU by utilizing NVIDIA's vGPU technology and come with a proprietary vGPU driver preinstalled.

| Flavor          | vCPUs | RAM(GB) | Local Storage (GB) | GPU Compute | GPU RAM (GB) | Cost per hour (SU) |
|:----------------|:-----:|:-------:|:------------------:|:-----------:|:------------:|:------------------:|
| g3.medium       |   8   |   30    |         60         | 25% of GPU  | 10           |       16           |
| g3.large[^largest] |  16   |   60    |         60         | 50% of GPU  | 20           |       32           |

### Full GPU

Full GPU instances have an entire NVIDIA GPU attached via PCI Passthrough and come with a generic (non-proprietary) NVIDIA driver. Users may find that launch times for new full card GPU instances take longer than normal. This is because we install the necessary GPU driver during initial setup. Also, due to technical limitations, we deter users from resizing full-card instances.

| Flavor          | vCPUs | RAM(GB) | Local Storage (GB) | NVIDIA GPU Type | GPU RAM (GB) | Cost per hour (SU) |
|:----------------|:-----:|:-------:|:------------------:|:-----------:|:------------:|:------------------:|
| g3.xl[^largest] |  32   |   120   |         60         | A100 | 40           |      64           |
| g4.xl[^largest]* |  12   |   120   |         60         | L40S | 48           |      84           |
| g4.2xl[^largest]* |  24   |   240   |         60         | L40S | 96           |      168           |
| g4.4xl[^largest]* |  48   |   480   |         60         | L40S | 192           |      336           |
| g5.xl[^largest]* |  20   |   240   |         60         | H100 | 80           |      128           |
| g5.2xl[^largest]* |  40   |   480   |         60         | H100 | 160           |      256           |
| g5.4xl[^largest]* |  80   |   960   |         60         | H100 | 320           |      512           |


\* *L40S and H100 flavors are not available by default. These flavors are available by submitting a request to [help@jetstream-cloud.org](mailto:help@jetstream-cloud.org) with proper justification.*

> 💡 Note
>    If you are using a partial-GPU flavor, and the remainder of the underlying physical GPU is idle, your instance may provide higher compute performance than the flavor strictly allots. In other words, the GPU compute for each flavor is a minimum value, while the GPU RAM is a maximum value.

**Jetstream2 instance types, flavors, and associated policies are subject to change in the future.**

[^largest]: Jetstream2 regularly exhausts its capacity to create instances of the largest flavors of each resource type. If you plan to use these, check the [availability dashboard](../overview/status.md/#availability-of-scarce-resources) to ensure there is space.

----

### Example of SU estimation:

> tip

    You can now estimate your SU needs using the usage estimation calculator here: [Usage Estimation Calculator](../alloc/estimator.md){target=_blank}

*   First determine the compute resource appropriate to your needs (CPU only, large memory, GPU):
    *   If your work requires 24 GB of RAM and 60 GB of local storage:
        *   you would request 8 SUs per hour to cover a single *m3.medium* instance.
    *   If your work requires 10 GB of local storage in 1 core using 3 GB of RAM:
        *   you would request 2 SUs per hour for an *m3.small* instance.
    *   If your work requires 1TB of RAM:
        *   you would request 256 SUs per hour for an *r3.xl* instance on Jetstream Large Memory
    *   If you work requires 20 GB of GPU RAM:
        *   you would request 32 SUs per hour for a *g3.large* instance on Jetstream GPU
*   You then would calculate for the appropriate resource (refer to the tables above):
    *   For Jetstream2 CPU, you would then multiply by the number of hours you will use that flavor instance in the next year and multiply by the number of instances you will need.
    *   For Jetstream2 Large Memory and GPU, either refer to the SU cost per hour in the last column, or multiply hours times 2
*   To calculate the number of SUs you will need in the next year, first estimate the number of hours you expect to work on a particular project.
    For example, if you typically work 40 hours per week and expect to spend 25% of your time on this project that would be 10 hours per week.
*   Next, calculate the total number of hours per year for this project:
    *   Total hours = 10 hours per week \* 52 weeks per year
    *   Total hours = 520
*   Finally, calculate the total SUs for the year for a single instance:
    *   Total SUs = 520 hours per year \* vCPUs
        *   e.g. For a Medium instance: Total SUs = 520 hours per year \* 8vCPUs
        *   Total SUs = 4160
*   If your project requires more than 1 instance, multiply the total SUs by the number of instances that you will need:
    *   Total SUs needed for 3 medium flavor instances = 3 \* 4160
    *   Total SUs = 12480

The calculations above assume that your instance is shelved when not in use.  For instructions see:

* [Cacao instance management actions](../ui/cacao/deployments.md){target=_blank}
* [Exosphere instance management actions](../ui/exo/manage.md){target=_blank}
* [Horizon instance management actions](../ui/horizon/manage.md){target=_blank}
* [Command line instance management actions](../ui/cli/manage.md){target=_blank}


##### SU Estimation for Infrastructure or "Always On" allocations

For jobs that may need to run for extended periods or as "always on" infrastructure, you can take this approach:

> instance cost (SUs) x 24 hours/day x 365 days = single instance cost per year

or as an example for each resource, an m3.large, r3.large, and g3.large each running for a year:

        m3.large (16 cores) x 24 hours/day x 365 days = 140,160 SUs
        r3.large (64 cores x 2 SUs/hour) x 24 hours/day x 365 days = 1,121,280 SUs
        g3.large (16 cores x 2 SUs/hour) x 24 hours/day x 365 days = 280,320 SUs

## Cost Estimation

You can get a dynamic cost estimate for your usage using the following command:

```bash
cmc vm cost
```

You can also override the default parameters to see how different configurations affect the cost:

```bash
cmc vm cost --flavor <flavor> --num_instances <number> --hours_per_day <hours> --days_per_week <days> --weeks <weeks>
```
