| Machine Type | vCPU | RAM | Cost per Hour |
|---|---|---|---|
| e2-micro | 2 | 1 GiB | Free Tier |
| e2-small | 2 | 2 GiB | $0.02 |
| e2-medium | 2 | 4 GiB | $0.04 |
| n1-standard-1 | 1 | 3.75 GiB | $0.0475 |

## Cost Estimation

You can get a dynamic cost estimate for your usage using the following command:

```bash
cmc vm cost
```

You can also override the default parameters to see how different configurations affect the cost:

```bash
cmc vm cost --flavor <flavor> --num_instances <number> --hours_per_day <hours> --days_per_week <days> --weeks <weeks>
```
