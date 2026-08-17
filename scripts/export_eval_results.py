import argparse
import json
from pathlib import Path

from azure.ai.projects import AIProjectClient
from azure.identity import AzureCliCredential


def serialize(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "as_dict"):
        return value.as_dict()
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-endpoint", required=True)
    parser.add_argument("--eval-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    client = AIProjectClient(
        endpoint=args.project_endpoint,
        credential=AzureCliCredential(),
    )
    openai_client = client.get_openai_client()
    items = [
        serialize(item)
        for item in openai_client.evals.runs.output_items.list(
            eval_id=args.eval_id,
            run_id=args.run_id,
        )
    ]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(items, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
