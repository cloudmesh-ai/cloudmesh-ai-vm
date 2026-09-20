| Instance Type | vCPU | RAM | Cost per Hour |
|---|---|---|---|
| Standard_B1s | 1 | 2 GiB | $0.01 |
| Standard_B2s | 2 | 4 GiB | $0.04 |
| Standard_D2s_v3 | 2 | 8 GiB | $0.096 |

## Cost Estimation

You can get a dynamic cost estimate for your usage using the following command:

```bash
cmc vm cost
```

You can also override the default parameters to see how different configurations affect the cost:

```bash
cmc vm cost --flavor <flavor> --num_instances <number> --hours_per_day <hours> --days_per_week <days> --weeks <weeks>
```
