# SupportAgent CI/CD lifecycle

This repository contains a Microsoft Foundry hosted agent and the pipeline that validates, evaluates, and promotes it.

## Agent

`azure.yaml` deploys `src/support-agent` as the hosted agent `SupportAgentHosted`.

The agent uses:

- Microsoft Agent Framework
- The OpenAI Responses protocol
- A Foundry Toolbox for ServiceNow and web-search tools
- Environment-specific Foundry projects and tool connections

The runtime is defined in `main.py`. Behaviour and safety boundaries are defined in `instructions.py`. The DEV and PROD toolbox files select the correct project-scoped ServiceNow connection without storing credentials in the repository.

## Source of truth

| Concern | Files |
|---|---|
| Hosted deployment | `azure.yaml`, `src/support-agent/agent.yaml` |
| Runtime | `src/support-agent/main.py`, `requirements.txt`, `Dockerfile` |
| Behaviour | `src/support-agent/instructions.py` |
| Tools | `src/support-agent/toolbox.dev.yaml`, `toolbox.prod.yaml` |
| Environment configuration | `config/dev.json`, `config/prod.json` |
| Release cases | `evals/release.json` |
| Release thresholds | `evals/thresholds.json` |
| Evaluator rubrics | `src/support-agent/evaluators` |
| CI/CD policy | `.github/workflows/ci.yml`, `.github/workflows/cd.yml` |

A source commit represents one complete agent candidate. DEV and PROD use different identities, endpoints, and tool connections, but they deploy the same reviewed source.

## Pull-request flow

Every pull request starts two checks.

The CI workflow:

1. Runs Ruff linting.
2. Runs a Bandit security scan.
3. Runs unit and manifest tests.
4. Validates the evaluation data.
5. Runs the local hosted-agent configuration doctor.

The deployment workflow:

1. Authenticates to Azure through GitHub OIDC.
2. Deploys the pull-request commit to the DEV Foundry project.
3. Verifies the hosted-agent status.
4. Runs agent and ServiceNow smoke tests.
5. Invokes every release case against the deployed candidate.
6. Scores the captured responses.
7. Enforces the release thresholds.

The DEV deployment and evaluation job is a required merge check.

## Evaluation

`scripts/run_eval_gate.py` owns the evaluation sequence:

1. `warm` confirms that the deployed endpoint is ready.
2. `collect` invokes the exact deployed agent version and stores its responses.
3. `score` uses the Azure AI Evaluation SDK to run fluency, task-adherence, and violence evaluators.
4. `score` also runs the source-controlled `support_quality` and `joke_instruction` custom rubrics.
5. `enforce` compares the results with `evals/thresholds.json`.

Invocation errors are reported separately from evaluator failures. The GitHub summary includes each test request, the agent response, custom evaluator results, scores, and reasons. The complete JSON report is uploaded as a workflow artifact.

## Production promotion

After a pull request is merged, the merged commit is deployed and evaluated in DEV again.

If it passes:

1. The workflow waits for approval on the protected `prod` GitHub Environment.
2. The same commit is deployed to the PROD Foundry project.
3. A new immutable hosted-agent version is created.
4. PROD agent and ServiceNow smoke tests verify the deployment.

There is no intermediate test environment. Promotion is DEV to approved PROD.
