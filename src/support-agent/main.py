import asyncio
import os

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import FoundryToolbox, ResponsesHostServer
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv
from instructions import AGENT_INSTRUCTIONS, DEV_SERVICENOW_MOCK_INSTRUCTIONS

load_dotenv()


async def main() -> None:
    credential = DefaultAzureCredential()
    toolbox = FoundryToolbox(credential)
    instructions = AGENT_INSTRUCTIONS
    if os.getenv("SERVICENOW_MODE") == "mock":
        instructions = f"{DEV_SERVICENOW_MOCK_INSTRUCTIONS}\n\n{instructions}"
    client = FoundryChatClient(
        project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
        model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
        credential=credential,
    )
    agent = Agent(
        client=client,
        instructions=instructions,
        tools=toolbox,
    )
    server = ResponsesHostServer(agent)
    await server.run_async()


if __name__ == "__main__":
    asyncio.run(main())
