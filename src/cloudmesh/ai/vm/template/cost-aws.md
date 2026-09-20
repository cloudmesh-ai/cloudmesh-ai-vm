| Instance Type | vCPU | RAM | Cost per Hour |
|---|---|---|---|
| t2.micro | 1 | 1 GiB | Free Tier |
| t2.small | 1 | 2 GiB | $0.0208 |
| t2.medium | 2 | 4 GiB | $0.0416 |
| m5.large | 2 | 8 GiB | $0.096 |

## Cost Estimation

You can get a dynamic cost estimate for your usage using the following command:

```bash
cmc vm cost
```

You can also override the default parameters to see how different configurations affect the cost:

```bash
cmc vm cost --flavor <flavor> --num_instances <number> --hours_per_day <hours> --days_per_week <days> --weeks <weeks>
```
