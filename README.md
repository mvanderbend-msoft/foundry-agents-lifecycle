# SupportAgent hosted-agent lifecycle

This demo adapts the structure from:

- [CI/CD for AI Agents on Microsoft Foundry](https://techcommunity.microsoft.com/blog/educatordeveloperblog/cicd-for-ai-agents-on-microsoft-foundry/4522218)
- [foundry-agents-lifecycle](https://github.com/ericchansen/foundry-agents-lifecycle)
- [foundry-cicd](https://github.com/leestott/foundry-cicd)

It uses Microsoft Learn's current hosted-agent deployment commands rather than the reference repositories' prompt-agent SDK deployment.

## Lifecycle

```text
Developer change
  -> Pull request
  -> CI: lint, security scan, tests, manifest dry-run
  -> Deploy pull-request commit to DEV
  -> DEV smoke test and evaluation (required merge check)
  -> Merge to main only after DEV passes
  -> Revalidate the merged commit in DEV
  -> PROD environment approval
  -> Deploy the same commit to PROD
  -> PROD smoke test
```

There is no test/QA environment. The only deployment environments are `dev` and `prod`.

## Key mental model

The repository is the source of truth:

| Component | Source |
|---|---|
| Agent runtime | `src/support-agent/main.py` |
| Instructions | `src/support-agent/instructions.py` |
| Tools | `src/support-agent/toolbox.dev.yaml`, `src/support-agent/toolbox.prod.yaml` |
| Hosted deployment | `azure.yaml` and `src/support-agent/agent.yaml` |
| Environment values | `config/dev.json` and `config/prod.json` |
| Evaluation cases | `evals/release.json` |
| CI policy | `.github/workflows/ci.yml` |
| Promotion policy | `.github/workflows/cd.yml` |

Each environment gets a new immutable hosted-agent version created from the same source commit. Environment-specific project IDs, endpoints, and toolboxes are applied from version-controlled configuration.

## Environments

| Environment | Foundry project | Deployment |
|---|---|---|
| DEV | `mvanderbend-9174-dev` | Automatic for pull requests and `main` |
| PROD | `mvanderbend-9174` | Required GitHub Environment approval |

The hosted agent is named `SupportAgentHosted` so it can coexist with the existing prompt agent `SupportAgent:13`.

## Hosted-agent architecture

- Microsoft Agent Framework
- OpenAI Responses protocol
- Direct code deployment with `azd deploy`
- Foundry Toolbox
- Project-scoped ServiceNow connections (`servicenowmcp-dev` and `servicenowmcp`)
- GitHub OIDC authentication

`FoundryToolbox` authenticates the hosted agent to Foundry. The toolbox uses the project-specific ServiceNow connection, so credentials aren't placed in code, images, or GitHub.

## Local validation

```powershell
py -3.12 -m pip install pytest ruff bandit PyYAML
ruff check src tests scripts
bandit -r src\support-agent -ll
pytest tests -v
```

For deployment setup and the demo script, see [docs/SETUP.md](docs/SETUP.md) and [docs/DEMO.md](docs/DEMO.md).

## Evaluation limitation

The preview `microsoft/ai-agent-evals@v3-beta` action compares agent versions in the same project. Keep the accepted baseline in DEV and compare each new candidate with it. The DEV report is reviewed at the protected PROD approval gate.

## Microsoft documentation

- [Hosted-agent CI/CD quickstart](https://learn.microsoft.com/en-gb/azure/foundry/agents/quickstarts/set-up-cicd-hosted-agent)
- [Use a toolbox with a hosted agent](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/use-toolbox-hosted-agent)
- [Author `azure.yaml`](https://learn.microsoft.com/azure/foundry/agents/how-to/author-azure-yaml)
- [Deploy hosted agents from source](https://learn.microsoft.com/azure/foundry/agents/how-to/deploy-hosted-agent-code)
- [Foundry evaluation GitHub Action](https://learn.microsoft.com/azure/foundry/how-to/evaluation-github-action)
