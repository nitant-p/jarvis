# Cloud trial before buying hardware

**Researched:** 20 October 2026. **Status:** Recommendation only; nothing provisioned.

## Recommendation

Validate the workflow on a rented Linux server before purchasing a dedicated home computer. Start CPU-only: 4 vCPUs, 8 GB RAM, and at least 40–60 GB SSD, with short recordings, a quantized 3–4B language model, and a small English speech model processed sequentially. These are engineering sizing estimates, not application benchmarks or a guarantee that every model fits.

For a first continuous trial, use a DigitalOcean Basic Regular 8 GB instance for a few days: approximately US$12 for seven days of instance existence. If available, Hetzner's European CX43 offers 16 GB at a lower monthly price, but its public listing currently marks it unavailable. Do not base the trial schedule on obtaining that capacity.

If 8 GB constrains useful models, move to 16 GB rather than conclude the product is not useful. An 8 GB trial tests a small-model implementation, not the upper limit of local AI quality. Use a GPU briefly only if a measured quality/latency problem warrants it.

## Privacy scope

Cloud-hosted models process data on a provider's hardware, even when we install and operate the models ourselves. This is different from the original owned-hardware requirement.

Proposed first test: synthetic goals, non-sensitive voice notes, and a separate test calendar. Real private goals remain local unless the user explicitly chooses a broader cloud trial. Encryption at rest and deleting audio do not make processing on a cloud VM equivalent to local processing. No accounts, servers, uploads, or calendar connections have been created.

## Minimum sizing

| Tier | Proposed specification | What it tests |
| --- | --- | --- |
| Website/planner only | 1–2 vCPU, 1–2 GB RAM, 20 GB SSD | Capture, forms, rules, and calendar integration; excludes running the full transcription/LLM workload. |
| Constrained full prototype | 2 vCPU, 4 GB RAM, 30–40 GB SSD | Very small quantized 1–3B model and small speech model, sequentially. Useful for experiments, but not the recommended product trial. |
| Practical starting trial | 4 vCPU, 8 GB RAM, 40–60 GB SSD | Short English voice notes and quantized 3–4B model with bounded context and one job at a time. |
| More comfortable CPU trial | 4–8 vCPU, 16 GB RAM, 60–80 GB SSD | Room to compare quantized 7–8B models, larger context, and speech-model choices. |
| Optional GPU experiment | About 12–16 GB+ VRAM, 16 GB+ system RAM | Faster inference/model comparisons; not a first-version requirement. A larger GPU can still be economical for a few hours. |

Memory must cover weights, context/KV cache, inference buffers, speech processing, OS, and application services. Avoid treating model file size as total required RAM. A VM's shared vCPUs also do not predict dedicated Mac performance.

## CPU hosting prices

All amounts below are **USD**, excluding applicable taxes and optional extras. No free credits or promotional offers are assumed. Monthly amounts are published caps where offered, not hourly prices multiplied by a universal month length.

| Provider / plan | vCPU / RAM / SSD | Hourly | Monthly | Scope / caveat |
| --- | --- | --- | --- | --- |
| DigitalOcean Basic Regular | 4 / 8 GiB / 160 GiB | $0.07143 | $48 | Shared CPU; start here for a short trial. |
| DigitalOcean Basic Regular | 8 / 16 GiB / 320 GiB | $0.14286 | $96 | More model headroom, still shared CPU. |
| AWS Lightsail Linux, public IPv4 | 2 / 8 GB / 160 GB | Prorated | $44 | Fewer vCPUs than the DO starting option; burstable CPU. |
| AWS Lightsail Linux, public IPv4 | 4 / 16 GB / 320 GB | Prorated | $84 | Straightforward bundled AWS option; burstable CPU. |
| AWS EC2 t3.xlarge Linux | 4 / 16 GiB / EBS extra | $0.1670 | About $121.91 compute at 730 hours | **US East (N. Virginia) reference**, not a Singapore quote. CPU credits, disks, and IP charges can add cost. |
| Hetzner CX33, European locations | 4 / 8 GB / 80 GB | $0.0160 | $9.99 | Published prices exclude IPv4 and tax; public listing says unavailable. |
| Hetzner CX43, European locations | 8 / 16 GB / 160 GB | $0.0296 | $18.49 | Same availability caveat; not a Singapore-region price. |

Sources: [DigitalOcean prices](https://www.digitalocean.com/pricing/droplets), [Lightsail prices](https://aws.amazon.com/lightsail/pricing/), [EC2 T3 regional reference rates](https://aws.amazon.com/ec2/instance-types/t3/), [Hetzner published price adjustment](https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/), and [Hetzner specifications/availability](https://www.hetzner.com/cloud/cost-optimized/).

Confirm the exact region and selected SKU before launch. DigitalOcean also offers newer separately priced configurations; the quoted Basic Regular bundle is the basis of this comparison. Singapore proximity is useful for uploads but not necessary for a non-sensitive batch trial.

### Billing behavior matters

- **DigitalOcean bundled plans:** Billing continues while powered off and ends when destroyed. A seven-day 8 GB trial is $0.07143 × 168 ≈ **$12.00**; the 16 GB option is approximately **$24.00**. Twenty hours are approximately $1.43/$2.86 only if the instances exist for just those twenty hours. [Billing rules](https://docs.digitalocean.com/products/droplets/details/pricing/).
- **Lightsail:** Deleting the instance ends its charges; attached resources can continue billing. Stopping it is not the same as deleting it. [Deletion and billing](https://docs.aws.amazon.com/lightsail/latest/userguide/delete-an-amazon-lightsail-instance.html).
- **EC2 On-Demand:** Stopping an EBS-backed instance ends compute usage charges, while EBS persists and remains billed. Useful for intermittent development sessions. [Instance lifecycle](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-lifecycle.html).
- **CPU limitations:** Lightsail has burst capacity; T3 Unlimited can incur surplus-credit charges. Basic DO instances use shared CPU. Benchmark repeated jobs, not only an initial burst. [Lightsail burst capacity](https://docs.aws.amazon.com/lightsail/latest/userguide/cpu-burst-capacity-accrual.html), [T3 credits](https://aws.amazon.com/ec2/instance-types/t3/).

**Intermittent AWS example:** At the quoted US East rate, twenty t3.xlarge running hours cost **$3.34 in compute**. If a 40 GB gp3 volume is retained for a month at $0.08/GB-month, storage adds **$3.20**. Twenty hours of an automatically assigned public IPv4 address at $0.005/hour add **$0.10**. Baseline total: **$6.64**, before CPU-credit surcharges, transfer, snapshots, and tax. A retained Elastic IP can accrue charges while the machine is stopped. Regional rates must be checked before deployment. [EBS pricing reference](https://aws.amazon.com/ebs/pricing/), [IPv4 pricing](https://aws.amazon.com/vpc/pricing/).

For a small trial, use one VM and local database storage. Managed databases, load balancers, Kubernetes, and NAT gateways are unnecessary costs at this stage. Backups, snapshots, domains, extra volumes, paid monitoring, and excess transfer are separate where applicable. Budget notifications are not a hard spending cap.

## Optional GPU comparison

Runpod's current public Pods listing includes an **RTX A5000 with 24 GB VRAM at $0.27/hour**, and an **L4 with 24 GB VRAM at $0.59/hour**. These are rental examples, not guarantees of regional inventory or a particular hosting tier. The cheaper listing should not be assumed equivalent to a dedicated-provider security offering. [Runpod pricing](https://www.runpod.io/pricing).

Ten active hours would therefore be **$2.70** or **$5.90** in GPU-instance rental, plus storage and applicable extras. Model downloads, environment setup, and idle running time count toward paid usage. At $0.27/hour, 730 continuously billed hours are **$197.10**, before storage, so this is attractive for short experiments rather than the initial always-on design.

Standard network storage below 1 TB is listed at $0.07/GB/month: 40 GB retained for a month would add **$2.80**, where that storage option is supported. Pod-local volume disks have different running/stopped rates. Check selected storage lifecycle and tier; do not assume stopping compute deletes storage charges. [Runpod storage/billing](https://github.com/runpod/docs/blob/main/accounts-billing/billing.mdx).

## Proposed low-cost validation plan

1. Build and package a portable Linux prototype; avoid reliance on a Mac-only calendar helper for the cloud trial. Use a separate Google-backed calendar visible in Apple Calendar for integration checks.
2. Start a CPU-only 8 GB/4 vCPU trial. Use synthetic examples and short, non-sensitive recordings; run speech and LLM inference sequentially.
3. Test dinner capture with missing details, relative dates, a conflict, a voice completion update, a vague goal requiring clarification, and a calendar edit.
4. Measure transcription accuracy, structured event accuracy, clarification quality, total response delay, peak RAM, and calendar correctness. Time setup and cold starts separately.
5. If inadequate, repeat the same examples with 16 GB and a stronger quantized model. Separate “model misunderstood” from “model is too slow.”
6. If quality is useful but CPU latency is frustrating, rent a GPU for 5–10 hours and repeat the same cases.
7. Run the useful version for several days to assess whether the capture and review habit is valuable. An intermittently stopped VM cannot test continuous availability or reliable evening prompts.
8. Preserve needed code/configuration/results on owned hardware, then remove trial resources when finished. Choose permanent hardware only after identifying the smallest useful model and acceptable latency.

**Proposed trial budget:** Start with **US$15–30**, not a hardware purchase. This can cover a week of the DO 8 GB instance and a modest GPU comparison, or a week of the 16 GB instance with little extra spend. This is a planning allowance, not an enforced cap or final quote.

**Decision limit:** Cloud testing can establish product usefulness and model requirements. It will not accurately predict a particular Mac mini's inference speed, energy consumption, or native iCloud/EventKit behavior. Those need device-specific validation later.
