import { getData, getFilters, setFilter } from '../state.js';

function getAvailableOptions(data, currentFilters) {
  const prompts = data.prompts;

  function matchesOtherFilters(p, excludeKey) {
    if (excludeKey !== 'agents' && currentFilters.agents.length
        && !currentFilters.agents.includes(p.agent_id)) return false;
    if (excludeKey !== 'models' && currentFilters.models.length
        && !currentFilters.models.includes(p.model)) return false;
    return true;
  }

  const agents = new Set();
  const models = new Set();

  for (const p of prompts) {
    if (matchesOtherFilters(p, 'agents')) agents.add(p.agent_id);
    if (matchesOtherFilters(p, 'models') && p.model) models.add(p.model);
  }

  return { agents, models };
}

export function renderFilterBar(container) {
  const data = getData();
  if (!data) return;

  const current = getFilters();
  const available = getAvailableOptions(data, current);

  container.innerHTML = `
    <div class="filter-bar">
      <select id="filter-agent">
        <option value="">All Assistants</option>
        ${data.filters.agents.filter(a => available.agents.has(a.id)).map(a =>
          `<option value="${a.id}" ${current.agents.includes(a.id) ? 'selected' : ''}>${a.name}</option>`
        ).join('')}
      </select>
      <select id="filter-model">
        <option value="">All Models</option>
        ${data.filters.models.filter(m => available.models.has(m)).map(m =>
          `<option value="${m}" ${current.models.includes(m) ? 'selected' : ''}>${m}</option>`
        ).join('')}
      </select>
    </div>
  `;

  for (const [id, key] of [['filter-agent', 'agents'], ['filter-model', 'models']]) {
    container.querySelector('#' + id).addEventListener('change', (e) => {
      const val = e.target.value;
      setFilter(key, val ? [val] : []);
    });
  }
}
