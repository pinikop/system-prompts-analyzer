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
