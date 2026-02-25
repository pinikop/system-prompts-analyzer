"""Orchestrates parse -> metrics -> JSON output."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from spa.config import DATA_DIR, WEB_DATA_DIR, load_agent_registry
from spa.metrics.rule_based import compute_metrics
from spa.metrics.tool_metrics import compute_tool_metrics
from spa.parsers.base import ToolDefinition
from spa.parsers.json_parser import parse_tools_json
from spa.parsers.txt_parser import extract_inline_tools, parse_prompt, parse_tools_txt
from spa.parsers.yaml_parser import parse_yaml_prompt


def _parse_prompt_file(path: Path, fmt: str) -> tuple:
    """Parse a prompt file and return (ParsedPrompt, list[ToolDefinition])."""
    text = path.read_text(encoding="utf-8")
    if fmt == "yaml":
        parsed = parse_yaml_prompt(text)
    else:
        parsed = parse_prompt(text)
    inline_tools = extract_inline_tools(text)
    return parsed, inline_tools


def _parse_tool_file(path: Path, fmt: str) -> list[ToolDefinition]:
    """Parse a separate tool definition file."""
    text = path.read_text(encoding="utf-8")
    if fmt == "txt":
        return parse_tools_txt(text).tools
    else:
        return parse_tools_json(text).tools


def _merge_tools(
    inline: list[ToolDefinition], file_tools: list[ToolDefinition]
) -> list[ToolDefinition]:
    """Merge inline and file-sourced tools, deduplicating by name."""
    seen: dict[str, ToolDefinition] = {}
    for t in inline:
        seen[t.name] = t
    for t in file_tools:
        if t.name not in seen:
            seen[t.name] = t
    return list(seen.values())


def run_pipeline(*, output_path: Path | None = None) -> dict:
    """Run the full analysis pipeline. Returns the output dict."""
    registry = load_agent_registry()

    if output_path is None:
        output_path = WEB_DATA_DIR / "analysis.json"

    prompts_out: list[dict] = []
    all_models: set[str] = set()
    all_agents: list[dict] = []
    all_vendors: set[str] = set()

    for agent_id, agent in registry.items():
        agent_name = agent["name"]
        vendor = agent.get("vendor", "Unknown")
        all_agents.append({"id": agent_id, "name": agent_name})
        all_vendors.add(vendor)

        # Parse separate tool files for this agent
        file_tools: list[ToolDefinition] = []
        for tool_entry in agent.get("tools", []):
            tool_path = DATA_DIR / tool_entry["path"]
            if tool_path.exists():
                fmt = tool_entry.get("format", "json")
                file_tools.extend(_parse_tool_file(tool_path, fmt))

        # Process each prompt
        for prompt_entry in agent.get("prompts", []):
            prompt_path = DATA_DIR / prompt_entry["path"]
            if not prompt_path.exists():
                continue

            fmt = prompt_entry.get("format", "txt")
            parsed, inline_tools = _parse_prompt_file(prompt_path, fmt)
            merged_tools = _merge_tools(inline_tools, file_tools)

            metrics = compute_metrics(parsed)
            tool_metrics = compute_tool_metrics(merged_tools)

            model = prompt_entry.get("model")
            if model:
                all_models.add(model)

            prompts_out.append({
                "agent_id": agent_id,
                "agent_name": agent_name,
                "vendor": vendor,
                "label": prompt_entry["label"],
                "model": model,
                "is_latest": prompt_entry.get("latest", False),
                "metrics": metrics,
                "tools": tool_metrics,
            })

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "meta": {
            "llm_model": None,
            "agent_count": len(all_agents),
            "prompt_count": len(prompts_out),
        },
        "prompts": prompts_out,
        "filters": {
            "models": sorted(all_models),
            "agents": all_agents,
            "vendors": sorted(all_vendors),
        },
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="System Prompts Analyzer")
    parser.add_argument(
        "--output", "-o", type=Path, default=None,
        help="Output JSON path (default: web/data/analysis.json)",
    )
    parser.add_argument("--skip-llm", action="store_true", default=True)
    args = parser.parse_args()

    result = run_pipeline(output_path=args.output)
    count = result["meta"]["prompt_count"]
    agents = result["meta"]["agent_count"]
    print(f"Analyzed {count} prompts from {agents} agents -> {args.output or WEB_DATA_DIR / 'analysis.json'}")


if __name__ == "__main__":
    main()
