# Operational Analysis POC

**Date:** 2026-02-28
**Status:** Design approved, ready for implementation

## Problem

The analyzer extracts thematic analysis (identity, tone, personality) but lacks insights into **how coding assistants are instructed to operate**. Users want to understand operational patterns like:
- When do assistants ask permission vs. act autonomously?
- What workflows do they follow (TDD, debugging approaches)?
- What safety constraints are enforced?
- How do they prefer to use tools?

## Goal

Create a **POC** that extracts and compares operational instructions across coding assistants, enabling:
- Pattern discovery (which assistants enforce TDD? Which require permission for destructive actions?)
- Quick comparison workflow (understand differences before choosing an assistant)
- Research/documentation (analyze different prompt engineering approaches)
- Learning tool (understand best practices in prompt design)

## Solution

**POC-focused approach** - Quick operational extraction for showcase, not production-ready.

### Architecture

Extend existing LLM analysis pipeline with minimal changes:
1. Add 4 new fields to `AssistantAnalysis` schema
2. Update extraction prompt to request operational data
3. Existing pipeline automatically extracts new fields
4. Add `/operations` route showing operational matrix view
5. Same data flow: `analysis.json` → UI reads and renders

**Key insight:** Just adding fields to existing LLM extraction, not building a separate system.

## LLM Schema Extension

**New fields added to `AssistantAnalysis` in `src/spa/llm/schemas.py`:**

```python
class AssistantAnalysis(BaseModel):
    # ... existing fields (identity, tone, personality, etc.) ...

    # New operational fields:
    permission_rules: list[str] = Field(
        description="3-5 rules about when assistant asks permission vs. acts autonomously",
        min_length=3,
        max_length=5,
    )
    workflow_approach: str = Field(
        description="1-2 sentences on workflow (TDD, debugging, planning methodology)"
    )
    safety_rules: list[str] = Field(
        description="3-5 key safety constraints or prohibited actions",
        min_length=3,
        max_length=5,
    )
    tool_philosophy: str = Field(
        description="1-2 sentences on tool usage preferences and patterns"
    )
```

**Why these fields:**
- `permission_rules` - Captures autonomy patterns (key differentiator)
- `workflow_approach` - Shows methodological differences (TDD vs. exploratory)
- `safety_rules` - Highlights constraint differences
- `tool_philosophy` - Shows how assistants think about their toolset

**Example output in analysis.json:**
```json
{
  "permission_rules": [
    "Ask before destructive operations (delete, force-push)",
    "Confirm before creating PRs or posting publicly",
    "Act autonomously for local edits and tests"
  ],
  "workflow_approach": "Strict TDD: write failing test, implement minimal code, refactor.",
  "safety_rules": [
    "Never commit credentials or secrets",
    "Never use --force flags without explicit permission",
    "Always verify tests pass before claiming completion"
  ],
  "tool_philosophy": "Prefer dedicated tools (Read/Edit) over shell commands (cat/sed)."
}
```

## Prompt Design

**Modification to `_build_prompt()` in `src/spa/llm/analyzer.py`:**

Add operational extraction instructions to existing prompt:

```python
def _build_prompt(raw_text: str, tool_names: list[str], assistant_name: str) -> str:
    tools = "\n".join(f"- {t}" for t in tool_names) if tool_names else "No tools defined."

    return f"""Analyze this system prompt for the coding assistant "{assistant_name}".

Extract thematic and operational information. Focus on:

**Operational Instructions:**
- permission_rules: When does it ask permission vs. act autonomously? Extract 3-5 specific rules.
- workflow_approach: What methodology does it follow (TDD, debugging process, planning)?
- safety_rules: What is it prohibited from doing? What must it always/never do? Extract 3-5 key rules.
- tool_philosophy: How should it use tools? Any preferences or constraints?

**Thematic Analysis (existing):**
- identity, tone, personality, behavioral_rules, unique_features, coding_philosophy...

**Available tools:**
{tools}

**System prompt to analyze:**
{raw_text}

Return valid JSON matching the AssistantAnalysis schema.
"""
```

**Why this works:**
- Pydantic schema auto-documents field requirements
- Simple, direct instructions - no fancy prompt engineering
- Existing infrastructure handles JSON parsing and validation
- Retry logic already exists for validation failures

## UI Component - Operational Matrix

**New route:** `/operations`

**Layout:**
- Table format: Rows = assistants, Columns = operational dimensions
- Columns:
  - Assistant Name
  - Permission Rules (expandable list)
  - Workflow Approach (text)
  - Safety Rules (expandable list)
  - Tool Philosophy (text)
- Filter integration (reuse existing vendor/assistant filters)
- Current prompts only (`is_current: true`)
- Expandable cells for lists

**Visual style:**
- Pico CSS (consistent with dashboard)
- Badge styling for list items
- Sticky header for scrolling
- Responsive grid

**Navigation:**
- Add "Operations" link to main nav
- Breadcrumb: Dashboard → Operations

**Files to create/modify:**
- Create: `web/js/views/operations.js`
- Modify: `web/js/app.js` (add `/operations` route)
- Modify: `web/index.html` (add nav link)

**Example row visualization:**
```
| Claude Code | • Ask before destructive ops        | Strict TDD with test-first    | • Never commit secrets     | Prefer Read/Edit over  |
|             | • Confirm before PRs                | discipline                    | • Never force-push         | shell commands         |
|             | • Act autonomously for local edits  |                               | • Verify tests pass        |                        |
```

## POC Scope

**Included:**
- ✅ 4 new operational fields in LLM schema
- ✅ Updated extraction prompt
- ✅ Operational matrix view (`/operations` route)
- ✅ Filter integration
- ✅ Current prompts only
- ✅ Manual testing on 5-8 assistants first

**Excluded (future iterations):**
- ❌ Side-by-side prompt viewer
- ❌ Diff view for version comparison
- ❌ Multi-way comparison (3+ assistants)
- ❌ LLM-generated comparative summaries
- ❌ Pattern discovery queries
- ❌ Export/sharing
- ❌ Historical tracking

**Success criteria:**
- Extract operational data from 5-8 assistants
- Matrix displays all 4 operational dimensions
- Filter bar works with matrix
- Data is readable and demonstrates concept
- Can showcase different operational approaches

## Compatibility with Other Plans

**LLM Config Cleanup:**
- No conflicts - just configuration changes
- ✅ Fully compatible

**Hybrid Data Fetching:**
- Beneficial - incremental caching for LLM results
- ⚠️ Initial run with new schema requires reprocessing all prompts (cache invalidation)
- After initial run, incremental caching works normally

**Execution order:**
1. LLM config cleanup (completed/in-progress)
2. Hybrid data fetching (in-progress)
3. **This POC** (next)

## Implementation Strategy

**Phase 1: Schema & Extraction (Backend)**
- Add 4 fields to `AssistantAnalysis`
- Update `_build_prompt()` with operational instructions
- Test on 2-3 prompts manually to verify extraction

**Phase 2: UI (Frontend)**
- Create `operations.js` view with matrix table
- Add route to `app.js`
- Add navigation link to `index.html`
- Test with existing analysis.json data

**Phase 3: Integration Testing**
- Run pipeline on 5-8 current prompts
- Verify operational data appears in matrix
- Test filtering
- Validate POC showcases the concept

**Time estimate:** 2-3 hours

## Future Productionization (Optional)

If POC is successful and you want to productionize:
- Refine extraction prompts for higher accuracy
- Add side-by-side prompt viewer
- Add diff view for version comparison
- Add LLM-generated comparative summaries
- Add pattern discovery queries
- Add export/sharing functionality
- Improve visualization (charts, graphs)
- Add historical tracking

## Benefits

- **Fast to build** - 2-3 hours for working POC
- **Low risk** - Extends existing infrastructure
- **Demonstrates value** - Shows operational pattern extraction works
- **Iterative** - Can refine or expand based on feedback
- **Cached** - Benefits from hybrid data fetching incremental processing
- **Educational** - Reveals how different assistants are instructed to operate
