import { getData, getFilters, setFilter, getFilteredPrompts } from '../state.js';

function getAvailableOptions(data, currentFilters) {
  const prompts = data.prompts;

  // For each filter, compute which options are valid given the OTHER active filters
  function matchesOtherFilters(p, excludeKey) {
    if (excludeKey !== 'vendors' && currentFilters.vendors.length
        && !currentFilters.vendors.includes(p.vendor)) return false;
    if (excludeKey !== 'agents' && currentFilters.agents.length
        && !currentFilters.agents.includes(p.agent_id)) return false;
    if (excludeKey !== 'models' && currentFilters.models.length
        && !currentFilters.models.includes(p.model)) return false;
    return true;
  }

  const vendors = new Set();
  const agents = new Set();
  const models = new Set();

  for (const p of prompts) {
    if (matchesOtherFilters(p, 'vendors')) vendors.add(p.vendor);
    if (matchesOtherFilters(p, 'agents')) agents.add(p.agent_id);
    if (matchesOtherFilters(p, 'models') && p.model) models.add(p.model);
  }

  return { vendors, agents, models };
}

export function renderFilterBar(container) {
  const data = getData();
  if (!data) return;

  const current = getFilters();
  const available = getAvailableOptions(data, current);

  const agentLookup = Object.fromEntries(
    data.filters.agents.map(a => [a.id, a.name])
  );

  container.innerHTML = `
    <div class="filter-bar">
      <select id="filter-vendor">
        <option value="">All Vendors</option>
        ${data.filters.vendors.filter(v => available.vendors.has(v)).map(v =>
          `<option value="${v}" ${current.vendors.includes(v) ? 'selected' : ''}>${v}</option>`
        ).join('')}
      </select>
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

  for (const [id, key] of [['filter-vendor', 'vendors'], ['filter-agent', 'agents'], ['filter-model', 'models']]) {
    container.querySelector('#' + id).addEventListener('change', (e) => {
      const val = e.target.value;
      setFilter(key, val ? [val] : []);
    });
  }
}
