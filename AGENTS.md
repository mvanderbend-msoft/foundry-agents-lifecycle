# Coding Agent Instructions

This project is a **Microsoft Foundry hosted agent** implemented with Microsoft Agent Framework and the Responses protocol.

## Key files

- `azure.yaml` — Foundry hosted-agent deployment manifest
- `src/support-agent/main.py` — hosted agent server
- `src/support-agent/instructions.py` — source-controlled behavior
- `src/support-agent/toolbox.*.yaml` — environment-specific ServiceNow MCP and web-search toolboxes
- `evals/release.json` — release evaluation dataset

## Development workflow

The Azure Developer CLI manages the lifecycle:

```powershell
python -m unittest discover -s tests -v
azd ai agent run
azd ai agent invoke --local "What tools can you use?"
azd deploy
azd ai agent invoke "What tools can you use?"
```

Do not store credentials in the repository. The environment-specific ServiceNow project connections contain downstream authentication configuration.

## Microsoft Foundry Skill

Install the **Microsoft Foundry Skill** for guided deployment, evaluation, and troubleshooting workflows.

Direct install (preferred, works with any coding agent):

```bash
npx skills add https://github.com/microsoft/azure-skills --skill microsoft-foundry
```

Or install the Azure Skills Plugin:

- **Copilot CLI**: `/plugin marketplace add microsoft/azure-skills` then `/plugin install azure@azure-skills`
- **Claude Code**: `/plugin install azure@claude-plugins-official`

Then ask naturally, e.g. `Use the Microsoft Foundry Skill to deploy this agent.`

## References

- [Hosted agents overview](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents)
- [Microsoft Foundry Skill](https://learn.microsoft.com/en-us/azure/foundry/how-to/develop/use-microsoft-foundry-skill)