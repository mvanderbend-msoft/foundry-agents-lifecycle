# Demo walkthrough

## Message

The agent lifecycle is code-first:

> Developers change the agent in Git. CI validates it. CD recreates it in DEV, evaluates it, and only an approved commit is recreated in PROD.

## Before the demo

1. Complete [SETUP.md](SETUP.md).
2. Configure the DEV baseline.
3. Add yourself as a required reviewer for `prod`.
4. Create a branch with a small change to `src/support-agent/instructions.py`.

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

Explain that no portal export is promoted. The pipeline applies the same repository state to each project.

## 2. Open the pull request

Show `.github/workflows/ci.yml`:

1. Ruff linting
2. Bandit security scan
3. Unit and manifest tests
4. Evaluation dataset validation
5. `azd ai agent doctor --local-only`

CI uses no Azure deployment identity.

## 3. Merge and deploy DEV

Show the `deploy-dev` job in `.github/workflows/cd.yml`:

1. Authenticate through the DEV GitHub OIDC identity.
2. Load `config/dev.json`.
3. Configure the `dev` azd environment.
4. Run `azd deploy --no-prompt`.
5. Verify status with `azd ai agent show`.
6. Invoke the hosted agent.
7. Run Foundry evaluation.
8. Compare with the accepted DEV baseline.

Discuss the workflow summary and evaluation report.

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
  -> DEV deployment
  -> DEV evaluation gate
  -> PROD approval
  -> PROD deployment
  -> production monitoring
```

The next maturity step is continuous evaluation over production traces, with failures curated into `evals/release.json`.
