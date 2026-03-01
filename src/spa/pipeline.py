"""Orchestrates parse -> metrics -> LLM analysis -> JSON output."""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn

from spa.config import DATA_DIR, DEFAULT_LLM_MODEL, WEB_DATA_DIR, load_assistant_registry
from spa.data_source import compute_file_hash
from spa.metrics.rule_based import compute_metrics
from spa.metrics.tool_metrics import compute_tool_metrics
from spa.parsers.base import ToolDefinition
from spa.parsers.json_parser import parse_tools_json
from spa.parsers.txt_parser import extract_inline_tools, parse_prompt, parse_tools_txt
from spa.parsers.yaml_parser import parse_yaml_prompt

logger = logging.getLogger(__name__)


class PipelineError(Exception):
    """Fatal pipeline error (missing credentials, etc.)."""


@dataclass
class _PromptResult:
    """Result of processing a single prompt through LLM analysis."""

    prompt_key: str
    analysis: object | None = None
    analysis_dict: dict | None = None
    token_usage: dict = field(
        default_factory=lambda: {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    )
    cached: bool = False
    error: str | None = None


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


def _compute_file_hashes(registry: dict) -> dict[str, str]:
    """Compute SHA256 hashes for all prompt files in the registry."""
    file_hashes: dict[str, str] = {}
    for assistant in registry.values():
        for prompt_entry in assistant.get("prompts", []):
            prompt_path = DATA_DIR / prompt_entry["path"]
            if prompt_path.exists():
                file_hashes[prompt_entry["path"]] = compute_file_hash(prompt_path)
    return file_hashes


@dataclass
class _ParsedEntry:
    """A parsed and measured prompt entry, ready for output."""

    entry: dict
    prompt_key: str
    raw_text: str
    tool_names: list[str]
    assistant_name: str
    path_str: str
    is_current: bool


def _parse_and_measure(registry: dict, skip_llm: bool) -> tuple[
    list[_ParsedEntry],
    list[dict],
    set[str],
    set[str],
]:
    """Parse all prompts and compute metrics.

    Returns (parsed_entries, all_assistants, all_models, all_vendors).
    """
    parsed_entries: list[_ParsedEntry] = []
    all_models: set[str] = set()
    all_assistants: list[dict] = []
    all_vendors: set[str] = set()

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

            parsed_entries.append(_ParsedEntry(
                entry=entry,
                prompt_key=prompt_key,
                raw_text=parsed.raw_text,
                tool_names=[t.name for t in merged_tools],
                assistant_name=assistant_name,
                path_str=prompt_entry["path"],
                is_current=is_current,
            ))

    return parsed_entries, all_assistants, all_models, all_vendors


def _process_prompt(
    prompt_key: str,
    raw_text: str,
    tool_names: list[str],
    assistant_name: str,
    llm_model: str,
    path_str: str | None,
    file_hashes: dict[str, str],
    previous_file_hashes: dict[str, str],
    previous_prompts: dict[str, dict],
) -> _PromptResult:
    """Analyze one prompt: check cache or call LLM. Returns results without side effects."""
    from spa.llm.analyzer import AuthenticationError, analyze_assistant
    from spa.llm.schemas import AssistantAnalysis

    # Check cache: reuse previous LLM analysis if file is unchanged
    if path_str and previous_prompts:
        current_hash = file_hashes.get(path_str)
        cached_hash = previous_file_hashes.get(path_str)
        if current_hash == cached_hash and prompt_key in previous_prompts:
            cached_llm = previous_prompts[prompt_key].get("llm_analysis")
            if cached_llm:
                logger.debug("  %s: using cached LLM analysis", prompt_key)
                return _PromptResult(
                    prompt_key=prompt_key,
                    analysis=AssistantAnalysis(**cached_llm),
                    analysis_dict=cached_llm,
                    cached=True,
                )

    try:
        analysis, usage = analyze_assistant(
            raw_text=raw_text,
            tool_names=tool_names,
            assistant_name=assistant_name,
            model=llm_model,
        )
    except AuthenticationError as e:
        raise PipelineError(f"Authentication failed: {e}\nCheck your LLM_API_KEY.") from e
    except Exception as e:
        error_type = type(e).__name__
        logger.error("LLM analysis failed for %s: %s", prompt_key, error_type)
        logger.debug("Full error: %s", e, exc_info=True)
        return _PromptResult(prompt_key=prompt_key, error=error_type)

    logger.debug(
        "  %s: %d tokens (in: %d, out: %d)",
        prompt_key,
        usage["total_tokens"],
        usage["prompt_tokens"],
        usage["completion_tokens"],
    )
    return _PromptResult(
        prompt_key=prompt_key,
        analysis=analysis,
        analysis_dict=analysis.model_dump(),
        token_usage=usage,
    )


def _run_llm_analysis(
    parsed_entries: list[_ParsedEntry],
    *,
    llm_model: str,
    file_hashes: dict[str, str],
    previous_file_hashes: dict[str, str],
    previous_prompts: dict[str, dict],
    skip_llm: bool,
) -> tuple[list[dict], dict[str, int], str | None]:
    """Run LLM analysis on current prompts and compute rankings.

    Returns (comparisons, total_tokens_used, llm_model_used).
    Mutates each entry's llm_analysis field in-place.
    """
    comparisons: list[dict] = []
    total_tokens_used = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    # Collect current prompts that need LLM analysis
    llm_entries = [e for e in parsed_entries if e.is_current and not skip_llm]
    if not llm_entries:
        return comparisons, total_tokens_used, None

    from spa.llm.rankings import compute_rankings
    from spa.llm.schemas import AssistantAnalysis

    analyses: dict[str, AssistantAnalysis] = {}
    prompts_out = [e.entry for e in parsed_entries]

    logger.info("Running LLM analysis on %d prompts...", len(llm_entries))

    def _apply_result(result: _PromptResult) -> str:
        """Apply an LLM result to shared state. Returns a status suffix for progress display."""
        if result.analysis is not None:
            analyses[result.prompt_key] = result.analysis
            aid, label = result.prompt_key.split("::", 1)
            for entry in prompts_out:
                if entry["assistant_id"] == aid and entry["label"] == label:
                    entry["llm_analysis"] = result.analysis_dict
                    break

        if not result.cached:
            total_tokens_used["prompt_tokens"] += result.token_usage["prompt_tokens"]
            total_tokens_used["completion_tokens"] += result.token_usage["completion_tokens"]
            total_tokens_used["total_tokens"] += result.token_usage["total_tokens"]

        if result.error:
            return f" - {result.error}"
        if result.cached:
            return " (cached)"
        return ""

    show_progress = logger.getEffectiveLevel() < logging.WARNING
    max_key_len = max(len(e.prompt_key) for e in llm_entries)

    def _process_all(on_update=None):
        for pe in llm_entries:
            if on_update:
                on_update(status="\u2807", name=pe.prompt_key, suffix=" ...")

            result = _process_prompt(
                prompt_key=pe.prompt_key,
                raw_text=pe.raw_text,
                tool_names=pe.tool_names,
                assistant_name=pe.assistant_name,
                llm_model=llm_model,
                path_str=pe.path_str,
                file_hashes=file_hashes,
                previous_file_hashes=previous_file_hashes,
                previous_prompts=previous_prompts,
            )

            suffix = _apply_result(result)

            if on_update:
                status = "\u2717" if result.error else "\u2713"
                on_update(advance=1, status=status, name=pe.prompt_key, suffix=suffix)

    if show_progress:
        with Progress(
            SpinnerColumn(),
            TextColumn("{task.fields[status]}", justify="left"),
            TextColumn("[bold blue]{task.fields[name]:<" + str(max_key_len) + "}"),
            TextColumn("{task.fields[suffix]}", justify="left"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        ) as progress:
            task = progress.add_task(
                "Analyzing prompts",
                total=len(llm_entries),
                status="",
                name="",
                suffix="",
            )

            def on_update(**kwargs) -> None:
                progress.update(task, **kwargs)

            _process_all(on_update)
    else:
        _process_all()

    if analyses:
        comparisons = compute_rankings(analyses, prompts_out)
        logger.info(
            "LLM analysis complete. Total tokens: %d (in: %d, out: %d)",
            total_tokens_used["total_tokens"],
            total_tokens_used["prompt_tokens"],
            total_tokens_used["completion_tokens"],
        )

    return comparisons, total_tokens_used, llm_model


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
        raise PipelineError(
            "LLM_API_KEY environment variable is required for LLM analysis.\n"
            "Set it in .env or pass --skip-llm to run without LLM analysis."
        )

    # Load previous analysis for incremental cache lookup
    previous_file_hashes: dict[str, str] = {}
    previous_prompts: dict[str, dict] = {}
    if not force and previous_analysis_path and previous_analysis_path.exists():
        try:
            prev_data = json.loads(previous_analysis_path.read_text())
            previous_file_hashes = prev_data.get("cache_info", {}).get("file_hashes", {})
            previous_prompts = {
                f"{p['assistant_id']}::{p['label']}": p for p in prev_data.get("prompts", [])
            }
        except (json.JSONDecodeError, KeyError):
            pass

    # Phase 1: Parse all prompts and compute metrics
    file_hashes = _compute_file_hashes(registry)
    parsed_entries, all_assistants, all_models, all_vendors = _parse_and_measure(
        registry, skip_llm
    )

    # Phase 2: Run LLM analysis on current prompts
    comparisons, total_tokens_used, llm_model_used = _run_llm_analysis(
        parsed_entries,
        llm_model=llm_model,
        file_hashes=file_hashes,
        previous_file_hashes=previous_file_hashes,
        previous_prompts=previous_prompts,
        skip_llm=skip_llm,
    )

    # Phase 3: Assemble and write output
    prompts_out = [e.entry for e in parsed_entries]
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
