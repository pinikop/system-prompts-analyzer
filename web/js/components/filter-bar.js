import { getData, getFilters, setFilter, toggleFilter } from '../state.js';

function getAvailableOptions(data, currentFilters) {
  const prompts = data.prompts.filter(p => p.is_current);

  function matchesOtherFilters(p, excludeKey) {
    if (excludeKey !== 'assistants' && currentFilters.assistants.length
        && !currentFilters.assistants.includes(p.assistant_id)) return false;
    if (excludeKey !== 'models' && currentFilters.models.length
        && !currentFilters.models.includes(p.model)) return false;
    return true;
  }

  const assistants = new Set();
  const models = new Set();

  for (const p of prompts) {
    if (matchesOtherFilters(p, 'assistants')) assistants.add(p.assistant_id);
    if (matchesOtherFilters(p, 'models') && p.model) models.add(p.model);
  }

  return { assistants, models };
}

export function renderFilterBar(container) {
  const data = getData();
  if (!data) return;

  const current = getFilters();
  const hasFilters = current.assistants.length > 0 || current.models.length > 0;
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
          ${data.filters.assistants.filter(a => available.assistants.has(a.id)).map(a =>
            `<span class="filter-chip ${current.assistants.includes(a.id) ? 'active' : ''}"
                  data-key="assistants" data-value="${a.id}">${a.name}</span>`
          ).join('')}
        </div>
      </div>
      ${modelSection}
      ${hasFilters ? '<div class="filter-group"><button class="outline secondary filter-clear">Clear all</button></div>' : ''}
    </div>
  `;

  container.querySelectorAll('.filter-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      toggleFilter(chip.dataset.key, chip.dataset.value);
    });
  });

  const clearBtn = container.querySelector('.filter-clear');
  if (clearBtn) {
    clearBtn.addEventListener('click', () => {
      setFilter('assistants', []);
      setFilter('models', []);
    });
  }
}
