# Operational Analysis POC Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extract and visualize operational instructions (permission rules, workflows, safety constraints, tool philosophy) from coding assistant prompts.

**Architecture:** Extend existing LLM schema with 4 new operational fields, update extraction prompt, create matrix view to display operational patterns across assistants.

**Tech Stack:** Python 3.12, Pydantic, litellm, vanilla JS, Pico CSS

---

## Task 1: Add operational fields to AssistantAnalysis schema

**Files:**
- Modify: `src/spa/llm/schemas.py`
- Test: `tests/test_llm.py`

**Step 1: Write failing test for new schema fields**

```python
# tests/test_llm.py (add after TestAssistantAnalysisSchema class, around line 73)

def test_operational_fields_required(self) -> None:
    """Operational fields are required and validated."""
    data = {**VALID_ANALYSIS}  # Start with valid base

    # Add operational fields
    data["permission_rules"] = [
        "Ask before destructive ops",
        "Confirm before PRs",
        "Act autonomously for edits",
    ]
    data["workflow_approach"] = "Strict TDD with test-first discipline."
    data["safety_rules"] = [
        "Never commit secrets",
        "Never force-push",
        "Always verify tests",
    ]
    data["tool_philosophy"] = "Prefer Read/Edit over shell commands."

    analysis = AssistantAnalysis(**data)
    assert len(analysis.permission_rules) == 3
    assert analysis.workflow_approach.startswith("Strict TDD")
    assert len(analysis.safety_rules) == 3
    assert "Read/Edit" in analysis.tool_philosophy


def test_permission_rules_length_validation(self) -> None:
    """permission_rules must have 3-5 items."""
    data = {**VALID_ANALYSIS, "permission_rules": ["only one"]}
    with pytest.raises(ValidationError):
        AssistantAnalysis(**data)
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_llm.py::TestAssistantAnalysisSchema::test_operational_fields_required -v
```
Expected: FAIL - `permission_rules` field missing

**Step 3: Add operational fields to schema**

```python
# src/spa/llm/schemas.py (add after error_handling field, around line 36)

class AssistantAnalysis(BaseModel):
    """LLM-extracted thematic analysis of one coding assistant's system prompt."""

    # ... existing fields ...

    error_handling: str = Field(description="1-2 sentence approach to errors")

    # New operational fields
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

**Step 4: Update VALID_ANALYSIS test fixture**

```python
# tests/test_llm.py (update VALID_ANALYSIS dict, around line 13)

VALID_ANALYSIS = {
    "identity": "A helpful coding assistant focused on productivity.",
    # ... existing fields ...
    "error_handling": "Investigates root causes before applying fixes.",

    # Add operational fields
    "permission_rules": [
        "Ask before destructive operations",
        "Confirm before creating PRs",
        "Act autonomously for local edits and tests",
    ],
    "workflow_approach": "Strict TDD: write failing test, implement minimal code, refactor.",
    "safety_rules": [
        "Never commit credentials or secrets",
        "Never use --force flags without explicit permission",
        "Always verify tests pass before claiming completion",
    ],
    "tool_philosophy": "Prefer dedicated tools (Read/Edit) over shell commands (cat/sed).",
}
```

**Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/test_llm.py::TestAssistantAnalysisSchema -v
```
Expected: All schema tests PASS

**Step 6: Commit**

```bash
git add src/spa/llm/schemas.py tests/test_llm.py
git commit -m "Add operational fields to AssistantAnalysis schema"
```

---

## Task 2: Update extraction prompt with operational instructions

**Files:**
- Modify: `src/spa/llm/analyzer.py`
- Test: `tests/test_llm.py`

**Step 1: Write test to verify prompt includes operational instructions**

```python
# tests/test_llm.py (add to TestPromptBuilding class, around line 123)

def test_prompt_includes_operational_instructions(self) -> None:
    """Prompt requests extraction of operational fields."""
    prompt = _build_prompt("some text", ["tool_a"], "TestBot")

    # Verify operational instructions are present
    assert "permission_rules" in prompt
    assert "workflow_approach" in prompt
    assert "safety_rules" in prompt
    assert "tool_philosophy" in prompt
    assert "When does it ask permission vs. act autonomously" in prompt
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_llm.py::TestPromptBuilding::test_prompt_includes_operational_instructions -v
```
Expected: FAIL - operational instructions not in prompt

**Step 3: Update _build_prompt() function**

```python
# src/spa/llm/analyzer.py (replace _build_prompt function, around line 32)

def _build_prompt(raw_text: str, tool_names: list[str], assistant_name: str) -> str:
    """Build LLM prompt for analyzing a coding assistant's system prompt."""
    tools = "\n".join(f"- {t}" for t in tool_names) if tool_names else "No tools defined."

    # Get schema description for field validation
    schema_desc = AssistantAnalysis.model_json_schema()

    return f"""Analyze this system prompt for the coding assistant "{assistant_name}".

Extract thematic and operational information. Focus on:

**Operational Instructions:**
- permission_rules: When does it ask permission vs. act autonomously? Extract 3-5 specific rules.
- workflow_approach: What methodology does it follow (TDD, debugging process, planning)?
- safety_rules: What is it prohibited from doing? What must it always/never do? Extract 3-5 key rules.
- tool_philosophy: How should it use tools? Any preferences or constraints?

**Thematic Analysis:**
- identity: {schema_desc['properties']['identity']['description']}
- tone: {schema_desc['properties']['tone']['description']}
- personality: {schema_desc['properties']['personality']['description']}
- behavioral_rules: {schema_desc['properties']['behavioral_rules']['description']}
- unique_features: {schema_desc['properties']['unique_features']['description']}
- coding_philosophy: {schema_desc['properties']['coding_philosophy']['description']}
- safety_emphasis: {schema_desc['properties']['safety_emphasis']['description']}
  Options: {', '.join(schema_desc['properties']['safety_emphasis']['enum'])}
- safety_details: {schema_desc['properties']['safety_details']['description']}
- autonomy_level: {schema_desc['properties']['autonomy_level']['description']}
  Options: {', '.join(schema_desc['properties']['autonomy_level']['enum'])}
- error_handling: {schema_desc['properties']['error_handling']['description']}

**Available tools:**
{tools}

**System prompt to analyze:**
{raw_text}

Return valid JSON matching the AssistantAnalysis schema.
"""
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_llm.py::TestPromptBuilding::test_prompt_includes_operational_instructions -v
```
Expected: PASS

**Step 5: Run all LLM tests**

```bash
uv run pytest tests/test_llm.py -v
```
Expected: All tests PASS

**Step 6: Commit**

```bash
git add src/spa/llm/analyzer.py tests/test_llm.py
git commit -m "Update extraction prompt with operational instructions"
```

---

## Task 3: Create operations view with matrix table

**Files:**
- Create: `web/js/views/operations.js`

**Step 1: Create operations.js with basic structure**

```javascript
// web/js/views/operations.js
import { getFilteredPrompts, subscribe } from '../state.js';
import { renderFilterBar } from '../components/filter-bar.js';

/**
 * Render operational analysis matrix comparing assistants.
 */
export function renderOperations(app) {
  function render() {
    const prompts = getFilteredPrompts().filter(p => p.is_current);

    app.innerHTML = `
      <nav aria-label="breadcrumb">
        <ul>
          <li><a href="#/">Dashboard</a></li>
          <li>Operations</li>
        </ul>
      </nav>
      <h2>Operational Analysis</h2>
      <p>Compare how different coding assistants are instructed to operate.</p>
      <div id="filter-container"></div>
      <div id="operations-table"></div>
    `;

    renderFilterBar(document.getElementById('filter-container'));
    renderMatrix(prompts, document.getElementById('operations-table'));
  }

  subscribe(render);
  render();
}

/**
 * Render operational matrix table.
 */
function renderMatrix(prompts, container) {
  if (prompts.length === 0) {
    container.innerHTML = '<p>No prompts match filters.</p>';
    return;
  }

  // Filter prompts with LLM analysis
  const analyzed = prompts.filter(p => p.llm_analysis);

  if (analyzed.length === 0) {
    container.innerHTML = `
      <p>No LLM analysis available. Run pipeline with LLM enabled:</p>
      <code>uv run spa</code>
    `;
    return;
  }

  const rows = analyzed.map(p => {
    const analysis = p.llm_analysis;
    return `
      <tr>
        <td>
          <strong>${p.assistant_name}</strong>
          ${p.model ? `<br><small>${p.model}</small>` : ''}
        </td>
        <td>${renderList(analysis.permission_rules)}</td>
        <td>${analysis.workflow_approach}</td>
        <td>${renderList(analysis.safety_rules)}</td>
        <td>${analysis.tool_philosophy}</td>
      </tr>
    `;
  }).join('');

  container.innerHTML = `
    <div style="overflow-x: auto;">
      <table>
        <thead>
          <tr>
            <th style="position: sticky; left: 0; background: var(--pico-background-color);">Assistant</th>
            <th>Permission Rules</th>
            <th>Workflow Approach</th>
            <th>Safety Rules</th>
            <th>Tool Philosophy</th>
          </tr>
        </thead>
        <tbody>
          ${rows}
        </tbody>
      </table>
    </div>
  `;
}

/**
 * Render a list of items as badges.
 */
function renderList(items) {
  if (!items || items.length === 0) return '-';

  return items.map(item =>
    `<span class="category-badge" style="display: block; margin: 0.25rem 0;">${item}</span>`
  ).join('');
}
```

**Step 2: Verify file structure**

```bash
cat web/js/views/operations.js | head -20
```
Expected: File created with renderOperations function

**Step 3: Commit**

```bash
git add web/js/views/operations.js
git commit -m "Create operations matrix view"
```

---

## Task 4: Add /operations route to app.js

**Files:**
- Modify: `web/js/app.js`

**Step 1: Read current routes**

```bash
grep -A 5 "function route" web/js/app.js
```

**Step 2: Add operations import and route**

```javascript
// web/js/app.js (add import at top, around line 3)
import { renderOperations } from './views/operations.js';

// web/js/app.js (add route in route() function, around line 15)
function route() {
  const hash = location.hash.replace(/\?.*$/, '') || '#/';
  const app = document.getElementById('app');

  // Strip query params for routing
  if (hash === '#/' || hash === '') {
    renderDashboard(app);
  } else if (hash.startsWith('#/assistant/')) {
    const id = hash.replace('#/assistant/', '');
    renderAssistantDetail(app, id);
  } else if (hash.startsWith('#/compare')) {
    renderCompare(app);
  } else if (hash === '#/operations') {
    renderOperations(app);
  } else {
    app.innerHTML = '<h2>404</h2><p>Page not found</p>';
  }
}
```

**Step 3: Verify syntax**

```bash
node -c web/js/app.js
```
Expected: No syntax errors

**Step 4: Commit**

```bash
git add web/js/app.js
git commit -m "Add /operations route to app router"
```

---

## Task 5: Add navigation link to index.html

**Files:**
- Modify: `web/index.html`

**Step 1: Read current nav**

```bash
grep -A 10 "<nav" web/index.html
```

**Step 2: Add Operations link**

```html
<!-- web/index.html (add to main nav, around line 15) -->
<nav>
  <ul>
    <li><strong>System Prompts Analyzer</strong></li>
  </ul>
  <ul>
    <li><a href="#/">Dashboard</a></li>
    <li><a href="#/compare">Compare</a></li>
    <li><a href="#/operations">Operations</a></li>
  </ul>
</nav>
```

**Step 3: Verify HTML is valid**

```bash
grep "Operations" web/index.html
```
Expected: Shows new link

**Step 4: Commit**

```bash
git add web/index.html
git commit -m "Add Operations link to main navigation"
```

---

## Task 6: Manual integration testing

**Files:**
- Test: Full POC workflow

**Step 1: Run pipeline with LLM on subset of prompts**

First, check which prompts are current:

```bash
uv run python -c "
import yaml
with open('agents.yaml') as f:
    agents = yaml.safe_load(f)
current = [p for a in agents['agents'] for p in a['prompts'] if p.get('current')]
print(f'Current prompts: {len(current)}')
for p in current[:5]:
    print(f\"  - {p.get('assistant_id')}::{p.get('label')}\")
"
```

Then run pipeline (requires LLM_API_KEY in .env):

```bash
uv run spa
```

Expected: Pipeline extracts operational fields for all prompts with LLM analysis

**Step 2: Check analysis.json for operational data**

```bash
uv run python -c "
import json
with open('web/data/analysis.json') as f:
    data = json.load(f)
prompt = data['prompts'][0]
if 'llm_analysis' in prompt and prompt['llm_analysis']:
    print(f\"Assistant: {prompt['assistant_name']}\")
    analysis = prompt['llm_analysis']
    print(f\"Permission rules: {len(analysis.get('permission_rules', []))} items\")
    print(f\"Workflow: {analysis.get('workflow_approach', 'N/A')[:50]}...\")
    print(f\"Safety rules: {len(analysis.get('safety_rules', []))} items\")
    print(f\"Tool philosophy: {analysis.get('tool_philosophy', 'N/A')[:50]}...\")
else:
    print('No LLM analysis found')
"
```

Expected: Shows operational data extracted from prompts

**Step 3: Open web UI and test operations view**

```bash
# Open web/index.html in browser or serve locally
python3 -m http.server 8000 --directory web
```

Then visit: http://localhost:8000
- Click "Operations" link in nav
- Verify matrix table displays
- Verify operational data shows for each assistant
- Test filter bar (vendor/assistant filters)
- Verify breadcrumb navigation works

Expected: Matrix displays operational patterns for current prompts

**Step 4: Verify POC showcases concept**

Manual checklist:
- [ ] Permission rules show autonomy differences
- [ ] Workflow approaches show TDD vs exploratory
- [ ] Safety rules show different constraint levels
- [ ] Tool philosophy shows tool preferences
- [ ] Filter bar narrows down assistants
- [ ] Table is readable and scannable
- [ ] Navigation works (Dashboard ↔ Operations)

**Step 5: Document any issues or improvements**

If extraction quality is poor:
- Check prompt engineering (may need refinement)
- Verify LLM model is capable (should be GPT-4 level)
- Check specific prompts that failed

If UI has issues:
- Check browser console for JS errors
- Verify analysis.json structure matches expectations
- Test responsive behavior on mobile

---

## Task 7: Final verification and documentation

**Files:**
- Test: All tests pass
- Verify: POC complete

**Step 1: Run full test suite**

```bash
uv run pytest -v
```
Expected: All tests PASS

**Step 2: Run linter**

```bash
uv run ruff check src tests
```
Expected: No issues

**Step 3: Check git status**

```bash
git status
git log --oneline -7
```
Expected:
- Clean working directory
- 6 commits for this POC (1 per task + initial)

**Step 4: Optional - Update CLAUDE.md**

Add to "Conventions" section:

```markdown
## Conventions

- The web UI uses Pico CSS (classless) with minimal custom CSS
- Python 3.12+, `uv` for deps, `ruff` for lint/format, `pytest` for tests
- Operational analysis available at `/operations` route (requires LLM analysis)
```

If updated:
```bash
git add CLAUDE.md
git commit -m "Document operational analysis route in CLAUDE.md"
```

---

## Summary

**What was built:**
1. Extended `AssistantAnalysis` schema with 4 operational fields
2. Updated LLM extraction prompt to request operational data
3. Created `/operations` matrix view showing operational patterns
4. Integrated with existing filter bar and navigation

**POC capabilities:**
- Extracts: permission rules, workflow approach, safety rules, tool philosophy
- Compares: Side-by-side operational patterns across assistants
- Filters: Vendor/assistant filtering works with operations view
- Shows: Which assistants enforce TDD, require permission, prefer certain tools

**Time estimate:** 2-3 hours (actual)

**Next steps (optional productionization):**
- Refine prompt engineering for better extraction accuracy
- Add side-by-side prompt viewer
- Add diff view for version comparison
- Add LLM-generated comparative summaries
- Add pattern discovery queries
- Add export/sharing functionality
