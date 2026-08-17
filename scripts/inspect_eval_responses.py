import argparse
import json
from pathlib import Path

import openai
from azure.ai.projects import AIProjectClient
from azure.identity import AzureCliCredential


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-endpoint", required=True)
    parser.add_argument("--items", type=Path, required=True)
    args = parser.parse_args()

    project = AIProjectClient(
        endpoint=args.project_endpoint,
        credential=AzureCliCredential(),
    )
    client = project.get_openai_client()
    items = json.loads(args.items.read_text(encoding="utf-8"))
    summaries = []

    for item in items:
        response_id = item["datasource_item"].get("response_id")
        summary = {
            "item": item["datasource_item_id"],
            "response_id": response_id,
        }
        try:
            response = client.responses.retrieve(response_id)
            summary.update(
                {
                    "status": response.status,
                    "error": response.error.model_dump()
                    if response.error is not None
                    else None,
                    "output_count": len(response.output),
                    "output_types": [output.type for output in response.output],
                }
            )
        except openai.OpenAIError as exc:
            summary["retrieve_error"] = str(exc)
        summaries.append(summary)

    print(json.dumps(summaries, indent=2))


if __name__ == "__main__":
    main()
