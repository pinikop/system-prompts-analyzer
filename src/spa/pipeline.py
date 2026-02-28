"""Orchestrates parse -> metrics -> LLM analysis -> JSON output."""

import argparse
import json
import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

from spa.config import DATA_DIR, DEFAULT_LLM_MODEL, WEB_DATA_DIR, load_assistant_registry
from spa.data_source import compute_file_hash
from spa.metrics.rule_based import compute_metrics
from spa.metrics.tool_metrics import compute_tool_metrics
from spa.parsers.base import ToolDefinition
from spa.parsers.json_parser import parse_tools_json
from spa.parsers.txt_parser import extract_inline_tools, parse_prompt, parse_tools_txt
from spa.parsers.yaml_parser import parse_yaml_prompt

logger = logging.getLogger(__name__)


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


def run_pipeline(
    *,
    output_path: Path | None = None,
    skip_llm: bool = False,
    llm_model: str = DEFAULT_LLM_MODEL,
    previous_analysis_path: Path | None = None,
    force: bool = False,
    skip_update: bool = False,
) -> dict:
    """Run the full analysis pipeline. Returns the output dict."""
    load_dotenv()
    registry = load_assistant_registry()

    if output_path is None:
        output_path = WEB_DATA_DIR / "analysis.json"

    # Validate LLM credentials early
    if not skip_llm and not os.environ.get("LLM_API_KEY"):
        print(
            "Error: LLM_API_KEY environment variable is required for LLM analysis.\n"
            "Set it in .env or pass --skip-llm to run without LLM analysis.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Load previous analysis for incremental cache lookup
    previous_file_hashes: dict[str, str] = {}
    previous_prompts: dict[str, dict] = {}
    if not force and previous_analysis_path and previous_analysis_path.exists():
        try:
            prev_data = json.loads(previous_analysis_path.read_text())
            previous_file_hashes = prev_data.get("cache_info", {}).get("file_hashes", {})
            previous_prompts = {
                f"{p['assistant_id']}::{p['label']}": p
                for p in prev_data.get("prompts", [])
            }
        except (json.JSONDecodeError, KeyError):
            pass

    prompts_out: list[dict] = []
    all_models: set[str] = set()
    all_assistants: list[dict] = []
    all_vendors: set[str] = set()
    # Track raw text and tool names for LLM analysis
    llm_inputs: dict[str, tuple[str, list[str], str]] = {}
    # Track prompt file paths for cache hash comparison
    prompt_paths: dict[str, str] = {}

    for assistant_id, assistant in registry.items():
        assistant_name = assistant["name"]
        vendor = assistant.get("vendor", "Unknown")
        all_assistants.append({"id": assistant_id, "name": assistant_name})
        all_vendors.add(vendor)

        # Parse separate tool files for this assistant
        file_tools: list[ToolDefinition] = []
        for tool_entry in assistant.get("tools", []):
            tool_path = DATA_DIR / tool_entry["path"]
            if tool_path.exists():
                fmt = tool_entry.get("format", "json")
                file_tools.extend(_parse_tool_file(tool_path, fmt))

        # Process each prompt
        for prompt_entry in assistant.get("prompts", []):
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

            is_current = prompt_entry.get("current", False)
            prompt_key = f"{assistant_id}::{prompt_entry['label']}"

            entry = {
                "assistant_id": assistant_id,
                "assistant_name": assistant_name,
                "vendor": vendor,
                "label": prompt_entry["label"],
                "model": model,
                "is_current": is_current,
                "metrics": metrics,
                "tools": tool_metrics,
                "llm_analysis": None,
            }
            prompts_out.append(entry)

            if is_current and not skip_llm:
                llm_inputs[prompt_key] = (
                    parsed.raw_text,
                    [t.name for t in merged_tools],
                    assistant_name,
                )
                prompt_paths[prompt_key] = prompt_entry["path"]

    # Run LLM analysis on current prompts
    comparisons: list[dict] = []
    llm_model_used = None
    total_tokens_used = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    if llm_inputs and not skip_llm:
        from spa.llm.analyzer import analyze_assistant
        from spa.llm.rankings import compute_rankings
        from spa.llm.schemas import AssistantAnalysis

        llm_model_used = llm_model
        analyses: dict[str, AssistantAnalysis] = {}

        logger.info("Running LLM analysis on %d prompts...", len(llm_inputs))

        for prompt_key, (raw_text, tool_names, assistant_name) in llm_inputs.items():
            # Check cache: reuse previous LLM analysis if file is unchanged
            path_str = prompt_paths.get(prompt_key)
            if path_str and previous_prompts:
                current_hash = compute_file_hash(DATA_DIR / path_str)
                cached_hash = previous_file_hashes.get(path_str)
                if current_hash == cached_hash and prompt_key in previous_prompts:
                    cached_llm = previous_prompts[prompt_key].get("llm_analysis")
                    if cached_llm:
                        logger.info("  %s: using cached LLM analysis", prompt_key)
                        analyses[prompt_key] = AssistantAnalysis(**cached_llm)
                        assistant_id, label = prompt_key.split("::", 1)
                        for entry in prompts_out:
                            if entry["assistant_id"] == assistant_id and entry["label"] == label:
                                entry["llm_analysis"] = cached_llm
                                break
                        continue

            try:
                analysis, usage = analyze_assistant(
                    raw_text=raw_text,
                    tool_names=tool_names,
                    assistant_name=assistant_name,
                    model=llm_model,
                )
                analyses[prompt_key] = analysis

                # Accumulate token usage
                total_tokens_used["prompt_tokens"] += usage["prompt_tokens"]
                total_tokens_used["completion_tokens"] += usage["completion_tokens"]
                total_tokens_used["total_tokens"] += usage["total_tokens"]

                logger.info(
                    "  %s: %d tokens (in: %d, out: %d)",
                    prompt_key,
                    usage["total_tokens"],
                    usage["prompt_tokens"],
                    usage["completion_tokens"],
                )

                # Attach to the matching prompt entry
                assistant_id, label = prompt_key.split("::", 1)
                for entry in prompts_out:
                    if entry["assistant_id"] == assistant_id and entry["label"] == label:
                        entry["llm_analysis"] = analysis.model_dump()
                        break
            except Exception:
                logger.exception("LLM analysis failed for %s", prompt_key)

        if analyses:
            comparisons = compute_rankings(analyses, prompts_out)
            logger.info(
                "LLM analysis complete. Total tokens: %d (in: %d, out: %d)",
                total_tokens_used["total_tokens"],
                total_tokens_used["prompt_tokens"],
                total_tokens_used["completion_tokens"],
            )

    # Compute file hashes for all processed prompt files
    file_hashes: dict[str, str] = {}
    for assistant in registry.values():
        for prompt_entry in assistant.get("prompts", []):
            prompt_path = DATA_DIR / prompt_entry["path"]
            if prompt_path.exists():
                file_hashes[prompt_entry["path"]] = compute_file_hash(prompt_path)

    output = {
        "generated_at": datetime.now(UTC).isoformat(),
        "cache_info": {
            "data_source_commit": None,
            "file_hashes": file_hashes,
        },
        "meta": {
            "llm_model": llm_model_used,
            "assistant_count": len(all_assistants),
            "prompt_count": len(prompts_out),
            "token_usage": total_tokens_used if llm_model_used else None,
        },
        "prompts": prompts_out,
        "comparisons": comparisons,
        "filters": {
            "models": sorted(all_models),
            "assistants": all_assistants,
            "vendors": sorted(all_vendors),
        },
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="System Prompts Analyzer")
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Output JSON path (default: web/data/analysis.json)",
    )
    parser.add_argument(
        "--skip-llm",
        action="store_true",
        default=False,
        help="Skip LLM analysis and only run rule-based metrics",
    )
    parser.add_argument(
        "--llm-model",
        type=str,
        default=DEFAULT_LLM_MODEL,
        help=f"LLM model to use (default: {DEFAULT_LLM_MODEL})",
    )
    args = parser.parse_args()

    result = run_pipeline(
        output_path=args.output,
        skip_llm=args.skip_llm,
        llm_model=args.llm_model,
    )
    count = result["meta"]["prompt_count"]
    assistants = result["meta"]["assistant_count"]
    llm_status = f" (LLM: {result['meta']['llm_model']})" if result["meta"]["llm_model"] else ""
    out = args.output or WEB_DATA_DIR / "analysis.json"
    print(f"Analyzed {count} prompts from {assistants} assistants{llm_status} -> {out}")


if __name__ == "__main__":
    main()
