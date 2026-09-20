| Resource | Cost |
|---|---|
| Local VM | Free |

## Cost Estimation

You can get a dynamic cost estimate for your usage using the following command:

```bash
cmc vm cost
```

You can also override the default parameters to see how different configurations affect the cost:

```bash
cmc vm cost --flavor <flavor> --num_instances <number> --hours_per_day <hours> --days_per_week <days> --weeks <weeks>
```
