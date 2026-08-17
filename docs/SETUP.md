# Setup

The project and model deployments already exist, so this demo doesn't provision new Foundry infrastructure. It configures the tools and hosted agent once, then GitHub Actions owns repeat deployments.

## 1. Review environment configuration

Environment values are committed in:

- `config/dev.json`
- `config/prod.json`

They contain no credentials.

| Environment | Project |
|---|---|
| DEV | `mvanderbend-9174-dev` |
| PROD | `mvanderbend-9174` |

Both projects require the `gpt-5.6-sol` model deployment.

## 2. Prepare ServiceNow connections

The Foundry account requires unique connection names for project-owned connections:

```text
DEV:  servicenowmcp-dev
PROD: servicenowmcp
```

The target MCP endpoint is:

```text
https://logicapp-343868.azurewebsites.net/api/mcpservers/servicenowmcp/mcp
```

Create the DEV connection with project-managed identity authentication. No downstream credential is copied into this repository.

```powershell
azd ai connection create servicenowmcp-dev `
  --project-endpoint "https://mvanderbend-9174-resource.services.ai.azure.com/api/projects/mvanderbend-9174-dev" `
  --kind remote-tool `
  --target "https://logicapp-343868.azurewebsites.net/api/mcpservers/servicenowmcp/mcp" `
  --auth-type project-managed-identity `
  --audience "https://ai.azure.com/" `
  --metadata "ARMID=/subscriptions/78bdf401-d648-4553-a6d0-68fdac0ef440/resourcegroups/michael-eu/providers/microsoft.web/sites/logicapp-343868" `
  --metadata "type=logic_app"
```

The Logic App authentication policy must allow both Foundry project managed identities:

- PROD: `5d6d59ec-ee9a-428d-b213-78ffa90908aa`
- DEV: `2ac36a6a-8dd8-4128-8e1e-aa03790d059a`

The underlying Azure managed API connection `service-now` must also report `Connected` and pass its test operation. If the connector returns HTTP 502 or `Function failed`, reauthorize it in the Azure portal; its stored basic-auth secret cannot be copied between projects or recovered by the pipeline.

## 3. Create Foundry Toolbox in DEV and PROD

```powershell
azd ext install microsoft.foundry
azd auth login
```

DEV:

```powershell
azd ai toolbox create support-agent-tools `
  --from-file .\src\support-agent\toolbox.dev.yaml `
  --project-endpoint "https://mvanderbend-9174-resource.services.ai.azure.com/api/projects/mvanderbend-9174-dev"
```

PROD:

```powershell
azd ai toolbox create support-agent-tools `
  --from-file .\src\support-agent\toolbox.prod.yaml `
  --project-endpoint "https://mvanderbend-9174-resource.services.ai.azure.com/api/projects/mvanderbend-9174"
```

Review and constrain write-capable ServiceNow tools before production use.

## 4. Bootstrap the hosted agent

Microsoft's hosted-agent CI/CD quickstart expects the project to have been successfully deployed once.

Configure DEV from `config/dev.json`:

```powershell
azd env new dev
azd env set AZURE_SUBSCRIPTION_ID 78bdf401-d648-4553-a6d0-68fdac0ef440
azd env set AZURE_LOCATION swedencentral
azd env set FOUNDRY_PROJECT_ENDPOINT "https://mvanderbend-9174-resource.services.ai.azure.com/api/projects/mvanderbend-9174-dev"
azd env set AZURE_AI_PROJECT_ID "/subscriptions/78bdf401-d648-4553-a6d0-68fdac0ef440/resourceGroups/michael-eu/providers/Microsoft.CognitiveServices/accounts/mvanderbend-9174-resource/projects/mvanderbend-9174-dev"
azd env set FOUNDRY_MODEL_NAME gpt-5.6-sol
azd env set TOOLBOX_NAME support-agent-tools
azd deploy
azd ai agent invoke "Without calling tools, state your two operational modes."
```

The existing prompt agent remains untouched. The hosted deployment is `SupportAgentHosted`.

## 5. Create GitHub environments

Create exactly:

- `dev`
- `prod`

Configure required reviewers and optional wait timers on `prod`. Restrict it to the `main` branch.

Set these variables in both environments:

| Variable | Purpose |
|---|---|
| `AZURE_CLIENT_ID` | Environment-specific federated identity |
| `AZURE_TENANT_ID` | Microsoft Entra tenant |
| `AZURE_SUBSCRIPTION_ID` | Azure subscription |

All project endpoints, resource IDs, model names, and toolbox names come from `config/*.json`.

## 6. Configure OIDC

Create environment-scoped federated credentials:

```text
repo:<owner>/<repository>:environment:dev
repo:<owner>/<repository>:environment:prod
```

Following Microsoft's hosted-agent quickstart, assign **Foundry User** and **Contributor** on each target Foundry project. Prefer separate identities for DEV and PROD.

## 7. Protect `main`

Require:

1. Pull requests.
2. The **CI - Validate Agent Changes** status check.
3. The **Deploy and Evaluate DEV** status check, including the thresholds in `evals/thresholds.json`.
4. At least one approving review.
5. No direct pushes.
6. PROD environment approval.
