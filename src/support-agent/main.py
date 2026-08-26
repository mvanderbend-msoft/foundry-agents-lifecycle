import asyncio
import os

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import FoundryToolbox, ResponsesHostServer
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv
from instructions import AGENT_INSTRUCTIONS, SERVICENOW_MOCK_INSTRUCTIONS

load_dotenv()


async def main() -> None:
    credential = DefaultAzureCredential()
    instructions = AGENT_INSTRUCTIONS
    servicenow_mode = os.getenv("SERVICENOW_MODE", "live")
    if servicenow_mode == "mock":
        instructions = f"{SERVICENOW_MOCK_INSTRUCTIONS}\n\n{instructions}"
        tools = []
    else:
        tools = FoundryToolbox(credential)
    client = FoundryChatClient(
        project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
        model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
        credential=credential,
    )
    agent = Agent(
        client=client,
        instructions=instructions,
        tools=tools,
    )
    server = ResponsesHostServer(agent)
    await server.run_async()


if __name__ == "__main__":
    asyncio.run(main())
