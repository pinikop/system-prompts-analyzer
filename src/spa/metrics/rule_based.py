"""Rule-based metrics computation for parsed prompts."""

import re

from spa.config import DIRECTIVE_KEYWORDS
from spa.parsers.base import ParsedPrompt
from spa.parsers.classifier import classify_sections

_EXAMPLE_RE = re.compile(r"<example[^>]*>", re.IGNORECASE)


def compute_metrics(prompt: ParsedPrompt) -> dict:
    """Compute rule-based metrics for a parsed prompt."""
    text = prompt.raw_text
    words = text.split()
    word_count = len(words)

    directive_keywords: dict[str, int] = {}
    directive_total = 0
    for kw in DIRECTIVE_KEYWORDS:
        pattern = re.compile(r"\b" + re.escape(kw) + r"\b")
        count = len(pattern.findall(text))
        if count > 0:
            directive_keywords[kw] = count
            directive_total += count

    directive_density = round(directive_total / max(word_count, 1) * 1000, 1)
    example_count = len(_EXAMPLE_RE.findall(text))
    sections_by_category = classify_sections(prompt.sections)

    return {
        "word_count": word_count,
        "line_count": len(text.strip().splitlines()),
        "char_count": len(text),
        "section_count": len(prompt.sections),
        "sections_by_category": sections_by_category,
        "directive_keywords": directive_keywords,
        "directive_count": directive_total,
        "directive_density": directive_density,
        "example_count": example_count,
        "format_type": prompt.format_type,
    }
