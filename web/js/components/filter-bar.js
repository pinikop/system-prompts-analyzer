import { getData, getFilters, toggleFilter } from '../state.js';

function getAvailableOptions(data, currentFilters) {
  const prompts = data.prompts.filter(p => p.is_latest);

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

  const modelSection = available.models.size > 0 ? `
    <div class="filter-group">
      <h4>Target Model</h4>
      <div class="filter-options">
        ${data.filters.models.filter(m => available.models.has(m)).map(m =>
          `<span class="filter-chip ${current.models.includes(m) ? 'active' : ''}"
                data-key="models" data-value="${m}">${m}</span>`
        ).join('')}
      </div>
    </div>` : '';

  container.innerHTML = `
    <div class="filter-bar">
      <div class="filter-group">
        <h4>Assistant</h4>
        <div class="filter-options">
          ${data.filters.agents.filter(a => available.agents.has(a.id)).map(a =>
            `<span class="filter-chip ${current.agents.includes(a.id) ? 'active' : ''}"
                  data-key="agents" data-value="${a.id}">${a.name}</span>`
          ).join('')}
        </div>
      </div>
      ${modelSection}
    </div>
  `;

  container.querySelectorAll('.filter-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      toggleFilter(chip.dataset.key, chip.dataset.value);
    });
  });
}
