# Demo walkthrough

## Message

The agent lifecycle is code-first:

> Developers change the agent in Git. CI validates it, the pull-request commit is deployed and evaluated in DEV, and only a passing change can merge. The merged commit is revalidated before approved promotion to PROD.

## Before the demo

1. Complete [SETUP.md](SETUP.md).
2. Add yourself as a required reviewer for `prod`.
3. Create a branch with a small change to `src/support-agent/instructions.py`.

## 1. Show the repository contract

Open:

- `src/support-agent/instructions.py`
- `src/support-agent/main.py`
- `src/support-agent/toolbox.dev.yaml`
- `src/support-agent/toolbox.prod.yaml`
- `azure.yaml`
- `config/dev.json`
- `config/prod.json`
- `evals/release.json`
- `evals/thresholds.json`

Explain that no portal export is promoted. The pipeline applies the same repository state to each project.

## 2. Open the pull request

Show `.github/workflows/ci.yml` and the `deploy-dev` job in `.github/workflows/cd.yml`:

1. Ruff linting
2. Bandit security scan
3. Unit and manifest tests
4. Evaluation dataset validation
5. `azd ai agent doctor --local-only`
6. Authenticate through the DEV GitHub OIDC identity.
7. Deploy the pull-request commit to DEV.
8. Run model and ServiceNow smoke checks.
9. Score the deployed candidate with Microsoft's Azure AI Evaluation SDK.
10. Enforce the score and error limits in `evals/thresholds.json`.

Discuss the workflow summary and evaluation report.

The branch protection rule requires both `Lint, Test, and Validate` and `Deploy and Evaluate DEV`, so the pull request cannot merge until both pass.

## 3. Merge and revalidate

Merge the pull request. The `main` workflow deploys and evaluates the merged commit in DEV again, ensuring the exact production candidate passes before approval.

## 4. Approve PROD

The `deploy-prod` job is blocked by the `prod` GitHub Environment.

After approval:

1. The same workflow commit is checked out.
2. The PROD OIDC identity is used.
3. `config/prod.json` selects the production project.
4. `azd deploy` creates a new immutable production version.
5. Status and smoke checks run.

There is no intermediate test environment.

## 5. Close the lifecycle

```text
Change
  -> PR validation
  -> PR commit deployed to DEV
  -> required DEV evaluation merge gate
  -> merge and revalidate main commit
  -> PROD approval
  -> PROD deployment
  -> production monitoring
```

The next maturity step is continuous evaluation over production traces, with failures curated into `evals/release.json`.
