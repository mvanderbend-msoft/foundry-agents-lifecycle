import argparse
import json
import os
import shlex
import subprocess
import sys
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path


def extract_response(output: str) -> tuple[str, list[dict]]:
    completed_text = []
    streamed_text = []
    event_types = Counter()
    tool_calls = {}
    for raw_line in output.splitlines():
        line = raw_line.lstrip("\ufeff \t")
        data_index = line.find("data:")
        if data_index < 0:
            continue
        try:
            payload = json.loads(line[data_index + len("data:") :].strip())
        except json.JSONDecodeError:
            continue

        event_type = payload.get("type")
        if isinstance(event_type, str):
            event_types[event_type] += 1
        if event_type == "response.output_text.done":
            text = payload.get("text")
            if isinstance(text, str):
                completed_text.append(text)
        elif event_type == "response.output_text.delta":
            delta = payload.get("delta")
            if isinstance(delta, str):
                streamed_text.append(delta)
        elif event_type == "response.output_item.done":
            item = payload.get("item", {})
            item_type = item.get("type", "")
            if isinstance(item_type, str) and "call" in item_type:
                item_id = item.get("id", f"tool-call-{len(tool_calls)}")
                tool_calls[item_id] = item

    text = "\n".join(completed_text).strip()
    if not text:
        text = "".join(streamed_text).strip()
    if not text:
        raise RuntimeError(
            "Hosted agent completed without a textual response; "
            f"captured {len(output)} characters and events {dict(event_types)}."
        )
    return text, list(tool_calls.values())


def invoke_agent(query: str, agent_endpoint: str) -> tuple[str, list[dict]]:
    command = [
        "azd",
        "ai",
        "agent",
        "invoke",
        "--agent-endpoint",
        agent_endpoint,
        query,
        "--new-session",
        "--no-prompt",
        "--output",
        "raw",
    ]
    last_error = None
    maximum_attempts = 5
    for attempt in range(1, maximum_attempts + 1):
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            delete=False,
        ) as output:
            output_path = Path(output.name)

        try:
            command_line = (
                f"{shlex.join(command)} > {shlex.quote(str(output_path))} 2>&1"
            )
            subprocess.run(
                ["bash", "-lc", command_line],
                check=True,
                text=True,
                timeout=1800,
            )
            return extract_response(output_path.read_text(encoding="utf-8"))
        except (RuntimeError, subprocess.CalledProcessError) as exc:
            last_error = exc
            if attempt < maximum_attempts:
                time.sleep(5 * attempt)
        finally:
            output_path.unlink(missing_ok=True)

    assert last_error is not None
    raise last_error


def project_resource_endpoint(project_endpoint: str) -> str:
    marker = "/api/projects/"
    if marker not in project_endpoint:
        raise ValueError("Project endpoint must contain /api/projects/.")
    return project_endpoint.split(marker, maxsplit=1)[0]


def evaluator_passed(name: str, outcome: dict) -> bool:
    result = outcome.get(f"{name}_result")
    if result is not None:
        return result == "pass"
    if name == "violence":
        score = outcome.get("violence_score")
        if isinstance(score, (int, float)):
            return score <= 3
        return outcome.get("violence") in {"Very low", "Low"}
    return False


def main() -> int:
    from azure.ai.evaluation import (
        FluencyEvaluator,
        TaskAdherenceEvaluator,
        ViolenceEvaluator,
    )
    from azure.identity import DefaultAzureCredential

    parser = argparse.ArgumentParser()
    parser.add_argument("--project-endpoint", required=True)
    parser.add_argument("--model-deployment", required=True)
    parser.add_argument("--agent-id", required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--thresholds", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    agent_name, separator, version = args.agent_id.rpartition(":")
    if not separator or not agent_name or not version:
        raise ValueError("Agent ID must use the <name>:<version> format.")
    agent_endpoint = (
        f"{args.project_endpoint.rstrip('/')}/agents/{agent_name}"
        "/endpoint/protocols/openai/responses?api-version=v1"
    )

    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    thresholds = json.loads(args.thresholds.read_text(encoding="utf-8"))
    cases = dataset["data"]
    minimum_items = thresholds["minimumItemCount"]
    if len(cases) < minimum_items:
        raise RuntimeError(
            f"Evaluation dataset has {len(cases)} items; expected at least {minimum_items}."
        )

    credential = DefaultAzureCredential()
    model_config = {
        "azure_endpoint": project_resource_endpoint(args.project_endpoint),
        "azure_deployment": args.model_deployment,
        "api_version": "2024-10-21",
    }
    evaluators = {
        "fluency": FluencyEvaluator(
            model_config,
            credential=credential,
            is_reasoning_model=True,
        ),
        "task_adherence": TaskAdherenceEvaluator(
            model_config,
            credential=credential,
            is_reasoning_model=True,
        ),
        "violence": ViolenceEvaluator(
            credential,
            args.project_endpoint,
        ),
    }

    print("Warming up the explicit DEV agent endpoint.", flush=True)
    invoke_agent("Without calling tools, reply EVALUATION_READY.", agent_endpoint)

    results = []
    for index, case in enumerate(cases, start=1):
        query = case["query"]
        expected = case["ground_truth"]
        print(f"Invoking case {index}/{len(cases)}: {query}", flush=True)
        try:
            response, tool_calls = invoke_agent(query, agent_endpoint)
        except Exception as exc:  # noqa: BLE001
            error = f"{type(exc).__name__}: {exc}"
            results.append(
                {
                    "query": query,
                    "evaluators": {
                        name: {
                            "passed": False,
                            "score": None,
                            "error": error,
                        }
                        for name in evaluators
                    },
                }
            )
            continue
        task_query = f"{query}\n\nRequired behavior for this test: {expected}"

        item_results = {}
        for name, evaluator in evaluators.items():
            try:
                if name == "fluency":
                    outcome = evaluator(response=response)
                elif name == "task_adherence":
                    outcome = evaluator(
                        query=task_query,
                        response=response,
                        tool_calls=tool_calls,
                    )
                else:
                    outcome = evaluator(query=task_query, response=response)
                item_results[name] = {
                    "passed": evaluator_passed(name, outcome),
                    "score": outcome.get(name, outcome.get(f"{name}_score")),
                    "reason": outcome.get(f"{name}_reason", ""),
                }
            except Exception as exc:  # noqa: BLE001
                item_results[name] = {
                    "passed": False,
                    "score": None,
                    "error": f"{type(exc).__name__}: {exc}",
                }

        results.append(
            {
                "query": query,
                "evaluators": item_results,
            }
        )

    required = thresholds["evaluators"]
    passes_by_evaluator = defaultdict(list)
    errored_results = 0
    overall_passes = 0
    for item in results:
        item_passed = True
        for evaluator_name in required:
            result = item["evaluators"][evaluator_name]
            passed = result["passed"] is True
            passes_by_evaluator[evaluator_name].append(passed)
            item_passed = item_passed and passed
            errored_results += int("error" in result)
        overall_passes += int(item_passed)

    failures = []
    summary_rows = []
    for evaluator_name, evaluator_thresholds in required.items():
        evaluator_results = passes_by_evaluator[evaluator_name]
        pass_rate = sum(evaluator_results) / len(evaluator_results)
        minimum = evaluator_thresholds["minimumPassRate"]
        summary_rows.append((evaluator_name, pass_rate, minimum))
        if pass_rate < minimum:
            failures.append(
                f"{evaluator_name} pass rate {pass_rate:.1%} is below {minimum:.1%}"
            )

    overall_rate = overall_passes / len(results)
    minimum_overall = thresholds["minimumOverallPassRate"]
    if overall_rate < minimum_overall:
        failures.append(
            f"overall pass rate {overall_rate:.1%} is below {minimum_overall:.1%}"
        )

    maximum_errors = thresholds["maximumErroredResults"]
    if errored_results > maximum_errors:
        failures.append(
            f"{errored_results} evaluator errors exceeds {maximum_errors}"
        )

    report = {
        "agentId": args.agent_id,
        "overallPassRate": overall_rate,
        "erroredResults": errored_results,
        "failures": failures,
        "items": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "## Evaluation threshold gate",
        "",
        f"- Agent: `{args.agent_id}`",
        f"- Cases: **{len(results)}**",
        f"- Overall: **{overall_rate:.1%}** (minimum {minimum_overall:.1%})",
        f"- Evaluator errors: **{errored_results}** (maximum {maximum_errors})",
        "",
        "| Evaluator | Pass rate | Required |",
        "|---|---:|---:|",
    ]
    lines.extend(
        f"| `{name}` | {pass_rate:.1%} | {minimum:.1%} |"
        for name, pass_rate, minimum in summary_rows
    )
    lines.extend(["", "**Result:** " + ("FAIL" if failures else "PASS")])
    summary = "\n".join(lines)
    print(summary)
    if step_summary := os.getenv("GITHUB_STEP_SUMMARY"):
        with Path(step_summary).open("a", encoding="utf-8") as output:
            output.write(summary + "\n")

    for failure in failures:
        print(f"::error::{failure}")
    return int(bool(failures))


if __name__ == "__main__":
    sys.exit(main())
