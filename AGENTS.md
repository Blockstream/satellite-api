# AGENTS

## Plan First

- Share a brief plan of intended infrastructure changes before editing Terraform.

## Safety & Hygiene

- Run `terraform fmt` and `terraform validate` in the touched Terraform stack before submitting changes.
- Prefer narrowly scoped DNS changes and avoid modifying unrelated records.

## Learned Context

- `terraform/modules/dns/blockstream-space.tf` manages the `blockstream.space` public Cloud DNS zone for satellite workloads; add ACME CNAME records here when certificate validation is needed.
- `terraform/variables.tf` indexes `local.context_variables` by `terraform.workspace`; use one of `staging|prod|testnet-prod|misc` (for example `TF_WORKSPACE=prod terraform validate`) because `default` workspace validation fails.
