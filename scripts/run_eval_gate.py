import argparse
import json
import os
import sys
import tempfile
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TERMINAL_RUN_STATUSES = {"completed", "failed", "canceled"}


def load_rubric_definitions(entries: list[str]) -> dict[str, dict[str, Any]]:
    definitions = {}
    for entry in entries:
        name, separator, path_value = entry.partition("=")
        if not separator or not name or not path_value:
            raise ValueError(
                "Custom evaluators must use the <name>=<definition-path> format."
            )
        raw_definition = json.loads(Path(path_value).read_text(encoding="utf-8"))
        if isinstance(raw_definition, dict):
            dimensions = raw_definition.get("dimensions")
        else:
            dimensions = raw_definition
        if not isinstance(dimensions, list) or not dimensions:
            raise ValueError(f"Custom evaluator {name} has no rubric dimensions.")
        for dimension in dimensions:
            if not dimension.get("id") or not dimension.get("description"):
                raise ValueError(
                    f"Custom evaluator {name} has an invalid rubric dimension."
                )
            weight = dimension.get("weight")
            if not isinstance(weight, int) or not 1 <= weight <= 10:
                raise ValueError(
                    f"Custom evaluator {name} has a weight outside 1-10."
                )
        definitions[name] = {"dimensions": dimensions}
    return definitions


def build_dataset_rows(dataset: dict[str, Any]) -> list[dict[str, str]]:
    rows = []
    for case in dataset["data"]:
        query = case["query"]
        expected_behavior = case["ground_truth"]
        rows.append(
            {
                "query": query,
                "expected_behavior": expected_behavior,
                "evaluation_query": (
                    f"{query}\n\nRequired behavior for this test: "
                    f"{expected_behavior}"
                ),
                "joke_evaluation_query": (
                    "Evaluate only whether the response includes a brief, "
                    "professional, harmless joke or playful punchline."
                ),
            }
        )
    return rows


def write_jsonl(rows: list[dict[str, str]], output_path: Path) -> None:
    output_path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )


def to_plain(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {key: to_plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_plain(item) for item in value]
    if hasattr(value, "model_dump"):
        return to_plain(value.model_dump(mode="json", by_alias=True))
    if hasattr(value, "as_dict"):
        return to_plain(value.as_dict())
    if hasattr(value, "__dict__"):
        return {
            key: to_plain(item)
            for key, item in vars(value).items()
            if not key.startswith("_")
        }
    return str(value)


def criterion_result(result: Any) -> tuple[str, dict[str, Any]]:
    raw = to_plain(result)
    name = raw.get("name") or raw.get("testing_criteria") or "unknown"
    passed = raw.get("passed")
    if passed is None:
        passed = raw.get("label") == "pass"
    normalized = {
        "passed": passed is True,
        "score": raw.get("score"),
        "reason": raw.get("reason", ""),
    }
    if error := raw.get("error"):
        normalized["error"] = str(error)
    return name, normalized


def build_report(
    *,
    evaluation_id: str,
    run: Any,
    agent_id: str,
    dataset_info: dict[str, str],
    custom_evaluators: list[str],
    required_evaluators: list[str],
    output_items: list[Any],
) -> dict[str, Any]:
    items = []
    for output_item in output_items:
        raw_item = to_plain(output_item)
        datasource_item = raw_item.get("datasource_item") or {}
        evaluators = dict(
            criterion_result(result)
            for result in raw_item.get("results") or []
        )
        for evaluator_name in required_evaluators:
            if evaluator_name not in evaluators:
                evaluators[evaluator_name] = {
                    "passed": False,
                    "score": None,
                    "error": (
                        f"Foundry returned no result for evaluator "
                        f"{evaluator_name}."
                    ),
                }
        items.append(
            {
                "query": datasource_item.get("query", ""),
                "response": (
                    datasource_item.get("sample.output_text")
                    or datasource_item.get("output_text")
                    or datasource_item.get("response")
                    or ""
                ),
                "status": raw_item.get("status"),
                "evaluators": evaluators,
            }
        )

    raw_run = to_plain(run)
    return {
        "evaluationId": evaluation_id,
        "evaluationRunId": raw_run.get("id"),
        "evaluationStatus": raw_run.get("status"),
        "reportUrl": raw_run.get("report_url"),
        "agentId": agent_id,
        "dataset": dataset_info,
        "customEvaluators": custom_evaluators,
        "cloudResultCounts": raw_run.get("result_counts"),
        "items": items,
    }


def create_rubric_evaluators(
    project_client: Any,
    definitions: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    from azure.ai.projects.models import (
        EvaluatorCategory,
        EvaluatorDefinitionType,
    )

    created = {}
    for name, definition in definitions.items():
        evaluator_name = f"support-agent-{name.replace('_', '-')}"
        created[name] = project_client.beta.evaluators.create_version(
            name=evaluator_name,
            evaluator_version={
                "name": evaluator_name,
                "categories": [EvaluatorCategory.QUALITY],
                "display_name": name.replace("_", " ").title(),
                "description": (
                    f"Source-controlled {name} release rubric for SupportAgent."
                ),
                "definition": {
                    "type": EvaluatorDefinitionType.RUBRIC,
                    "dimensions": definition["dimensions"],
                    "pass_threshold": 0.5,
                },
            },
        )
    return created


def create_testing_criteria(
    model_deployment: str,
    rubric_evaluators: dict[str, Any],
) -> list[Any]:
    from azure.ai.projects.models import TestingCriterionAzureAIEvaluator

    criteria = [
        TestingCriterionAzureAIEvaluator(
            type="azure_ai_evaluator",
            name="fluency",
            evaluator_name="builtin.fluency",
            initialization_parameters={"deployment_name": model_deployment},
            data_mapping={"response": "{{sample.output_text}}"},
        ),
        TestingCriterionAzureAIEvaluator(
            type="azure_ai_evaluator",
            name="task_adherence",
            evaluator_name="builtin.task_adherence",
            initialization_parameters={"deployment_name": model_deployment},
            data_mapping={
                "query": "{{item.evaluation_query}}",
                "response": "{{sample.output_items}}",
            },
        ),
        TestingCriterionAzureAIEvaluator(
            type="azure_ai_evaluator",
            name="violence",
            evaluator_name="builtin.violence",
            data_mapping={
                "query": "{{item.query}}",
                "response": "{{sample.output_text}}",
            },
        ),
    ]
    for name, evaluator in rubric_evaluators.items():
        query_field = (
            "joke_evaluation_query"
            if name == "joke_instruction"
            else "query"
        )
        criteria.append(
            TestingCriterionAzureAIEvaluator(
                type="azure_ai_evaluator",
                name=name,
                evaluator_name=evaluator.name,
                initialization_parameters={
                    "deployment_name": model_deployment
                },
                data_mapping={
                    "query": f"{{{{item.{query_field}}}}}",
                    "response": "{{sample.output_items}}",
                },
            )
        )
    return criteria


def run_cloud_evaluation(
    project_endpoint: str,
    model_deployment: str,
    agent_id: str,
    dataset_path: Path,
    dataset_version: str,
    output_path: Path,
    custom_evaluator_entries: list[str],
    poll_interval: int,
) -> None:
    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential
    from openai.types.eval_create_params import DataSourceConfigCustom

    agent_name, separator, agent_version = agent_id.rpartition(":")
    if not separator or not agent_name or not agent_version:
        raise ValueError("Agent ID must use the <name>:<version> format.")

    dataset_definition = json.loads(dataset_path.read_text(encoding="utf-8"))
    rows = build_dataset_rows(dataset_definition)
    rubric_definitions = load_rubric_definitions(custom_evaluator_entries)
    required_evaluators = [
        "fluency",
        "task_adherence",
        "violence",
        *rubric_definitions,
    ]
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d%H%M%S")

    credential = DefaultAzureCredential()
    project_client = AIProjectClient(
        endpoint=project_endpoint,
        credential=credential,
    )
    openai_client = project_client.get_openai_client()
    try:
        with tempfile.TemporaryDirectory() as directory:
            jsonl_path = Path(directory) / "release.jsonl"
            write_jsonl(rows, jsonl_path)
            dataset = project_client.datasets.upload_file(
                name=dataset_definition["name"],
                version=dataset_version,
                file_path=str(jsonl_path),
            )

        rubric_evaluators = create_rubric_evaluators(
            project_client,
            rubric_definitions,
        )
        testing_criteria = create_testing_criteria(
            model_deployment,
            rubric_evaluators,
        )
        data_source_config = DataSourceConfigCustom(
            type="custom",
            item_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "expected_behavior": {"type": "string"},
                    "evaluation_query": {"type": "string"},
                    "joke_evaluation_query": {"type": "string"},
                },
                "required": [
                    "query",
                    "expected_behavior",
                    "evaluation_query",
                    "joke_evaluation_query",
                ],
            },
            include_sample_schema=True,
        )
        evaluation = openai_client.evals.create(
            name=f"{dataset_definition['name']}-{agent_version}-{timestamp}",
            data_source_config=data_source_config,
            testing_criteria=testing_criteria,
        )
        eval_run = openai_client.evals.runs.create(
            eval_id=evaluation.id,
            name=f"{agent_name}-{agent_version}-{timestamp}",
            metadata={
                "agent_name": agent_name,
                "agent_version": agent_version,
                "dataset_version": dataset_version,
            },
            data_source={
                "type": "azure_ai_target_completions",
                "source": {"type": "file_id", "id": dataset.id},
                "input_messages": {
                    "type": "template",
                    "template": [
                        {
                            "type": "message",
                            "role": "user",
                            "content": {
                                "type": "input_text",
                                "text": "{{item.query}}",
                            },
                        }
                    ],
                },
                "target": {
                    "type": "azure_ai_agent",
                    "name": agent_name,
                    "version": agent_version,
                },
            },
        )

        print(
            f"Foundry evaluation {evaluation.id}, run {eval_run.id} started.",
            flush=True,
        )
        while eval_run.status not in TERMINAL_RUN_STATUSES:
            time.sleep(poll_interval)
            eval_run = openai_client.evals.runs.retrieve(
                run_id=eval_run.id,
                eval_id=evaluation.id,
            )
            print(f"Evaluation status: {eval_run.status}", flush=True)

        output_items = list(
            openai_client.evals.runs.output_items.list(
                run_id=eval_run.id,
                eval_id=evaluation.id,
            )
        )
        report = build_report(
            evaluation_id=evaluation.id,
            run=eval_run,
            agent_id=agent_id,
            dataset_info={
                "name": dataset.name,
                "version": dataset.version,
                "id": dataset.id,
            },
            custom_evaluators=list(rubric_definitions),
            required_evaluators=required_evaluators,
            output_items=output_items,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(report, indent=2),
            encoding="utf-8",
        )
        if report_url := report.get("reportUrl"):
            print(f"Foundry report: {report_url}")
        if eval_run.status != "completed":
            raise RuntimeError(
                f"Foundry evaluation finished with status {eval_run.status}."
            )
    finally:
        openai_client.close()
        project_client.close()
        credential.close()


def enforce_thresholds(output_path: Path, thresholds_path: Path) -> int:
    report = json.loads(output_path.read_text(encoding="utf-8"))
    thresholds = json.loads(thresholds_path.read_text(encoding="utf-8"))
    results = report["items"]
    minimum_items = thresholds["minimumItemCount"]
    if len(results) < minimum_items:
        raise RuntimeError(
            f"Evaluation returned {len(results)} items; expected at least {minimum_items}."
        )

    required = thresholds["evaluators"]
    passes_by_evaluator = defaultdict(list)
    errors_by_evaluator = Counter()
    errored_results = 0
    errored_cases = 0
    overall_passes = 0
    for item in results:
        item_passed = True
        item_errored = False
        for evaluator_name in required:
            result = item["evaluators"][evaluator_name]
            if "error" in result:
                errors_by_evaluator[evaluator_name] += 1
                errored_results += 1
                item_errored = True
                item_passed = False
                continue
            passed = result["passed"] is True
            passes_by_evaluator[evaluator_name].append(passed)
            item_passed = item_passed and passed
        errored_cases += int(item_errored)
        overall_passes += int(item_passed)

    failures = []
    summary_rows = []
    for evaluator_name, evaluator_thresholds in required.items():
        evaluator_results = passes_by_evaluator[evaluator_name]
        pass_rate = (
            sum(evaluator_results) / len(evaluator_results)
            if evaluator_results
            else 0.0
        )
        minimum = evaluator_thresholds["minimumPassRate"]
        summary_rows.append(
            (
                evaluator_name,
                pass_rate,
                sum(evaluator_results),
                len(evaluator_results),
                errors_by_evaluator[evaluator_name],
                minimum,
            )
        )
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

    report.update(
        {
            "overallPassRate": overall_rate,
            "erroredResults": errored_results,
            "erroredCases": errored_cases,
            "failures": failures,
        }
    )
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "## Foundry cloud evaluation gate",
        "",
        f"- Agent: `{report['agentId']}`",
        f"- Cases: **{len(results)}**",
        f"- Overall: **{overall_rate:.1%}** (minimum {minimum_overall:.1%})",
        f"- Cases with errors: **{errored_cases}**",
        f"- Evaluator errors: **{errored_results}** (maximum {maximum_errors})",
    ]
    if report_url := report.get("reportUrl"):
        lines.append(f"- [Open the evaluation in Foundry]({report_url})")
    custom_evaluators = report.get("customEvaluators", [])
    if custom_evaluators:
        lines.append(
            "- Custom evaluators: "
            + ", ".join(f"`{name}`" for name in custom_evaluators)
        )
    lines.extend(
        [
            "",
            "| Evaluator | Pass rate | Scored | Errors | Required |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    lines.extend(
        f"| `{name}` | {pass_rate:.1%} | {passed}/{scored} | {errors} | "
        f"{minimum:.1%} |"
        for name, pass_rate, passed, scored, errors, minimum in summary_rows
    )
    failed_items = [
        (index, item)
        for index, item in enumerate(results, start=1)
        if not all(
            item["evaluators"][name].get("passed") is True
            for name in required
        )
    ]
    if failed_items:
        lines.extend(["", "## Failed cases"])
        for index, item in failed_items:
            lines.extend(["", f"### Case {index}", "", f"**Query:** {item['query']}"])
            for name in required:
                result = item["evaluators"][name]
                if result.get("passed") is True:
                    continue
                detail = (
                    result.get("error")
                    or result.get("reason")
                    or "No reason returned."
                )
                lines.append(
                    f"- **{name}:** score `{result.get('score')}` - {detail}"
                )
            if response := item.get("response"):
                lines.extend(["", "**Agent response:**", "", f"> {response}"])

    lines.extend(["", "## Case evidence"])
    for index, item in enumerate(results, start=1):
        case_passed = all(
            item["evaluators"][name].get("passed") is True
            for name in required
        )
        lines.extend(
            [
                "",
                "<details>",
                f"<summary>Case {index} - {'PASS' if case_passed else 'FAIL'}</summary>",
                "",
                f"**Query:** {item['query']}",
            ]
        )
        if response := item.get("response"):
            quoted_response = "\n".join(
                f"> {line}" for line in response.splitlines()
            )
            lines.extend(["", "**Agent response:**", "", quoted_response])
        if custom_evaluators:
            lines.extend(["", "**Custom evaluator results:**"])
            for name in custom_evaluators:
                result = item["evaluators"][name]
                status = "PASS" if result.get("passed") is True else "FAIL"
                detail = (
                    result.get("error")
                    or result.get("reason")
                    or "No reason returned."
                )
                lines.append(
                    f"- `{name}`: **{status}**, score `{result.get('score')}` - "
                    f"{detail}"
                )
        lines.extend(["", "</details>"])

    lines.extend(["", "**Result:** " + ("FAIL" if failures else "PASS")])
    summary = "\n".join(lines)
    print(summary)
    if step_summary := os.getenv("GITHUB_STEP_SUMMARY"):
        with Path(step_summary).open("a", encoding="utf-8") as output:
            output.write(summary + "\n")

    for failure in failures:
        print(f"::error::{failure}")
    return int(bool(failures))


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="stage", required=True)

    cloud_parser = subparsers.add_parser("cloud")
    cloud_parser.add_argument("--project-endpoint", required=True)
    cloud_parser.add_argument("--model-deployment", required=True)
    cloud_parser.add_argument("--agent-id", required=True)
    cloud_parser.add_argument("--dataset", type=Path, required=True)
    cloud_parser.add_argument("--dataset-version", required=True)
    cloud_parser.add_argument("--output", type=Path, required=True)
    cloud_parser.add_argument("--poll-interval", type=int, default=10)
    cloud_parser.add_argument(
        "--custom-evaluator",
        action="append",
        default=[],
        help="Custom evaluator in the <name>=<definition-path> format.",
    )

    enforce_parser = subparsers.add_parser("enforce")
    enforce_parser.add_argument("--thresholds", type=Path, required=True)
    enforce_parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if args.stage == "cloud":
        run_cloud_evaluation(
            args.project_endpoint,
            args.model_deployment,
            args.agent_id,
            args.dataset,
            args.dataset_version,
            args.output,
            args.custom_evaluator,
            args.poll_interval,
        )
        return 0
    return enforce_thresholds(args.output, args.thresholds)


if __name__ == "__main__":
    sys.exit(main())
