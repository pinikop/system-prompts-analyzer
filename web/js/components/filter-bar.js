import { getData, getFilters, setFilter } from '../state.js';

export function renderFilterBar(container) {
  const data = getData();
  if (!data) return;

  const filters = data.filters;
  const current = getFilters();

  container.innerHTML = `
    <div class="filter-bar">
      <select id="filter-agent">
        <option value="">All Agents</option>
        ${filters.agents.map(a =>
          `<option value="${a.id}" ${current.agents.includes(a.id) ? 'selected' : ''}>${a.name}</option>`
        ).join('')}
      </select>
      <select id="filter-vendor">
        <option value="">All Vendors</option>
        ${filters.vendors.map(v =>
          `<option value="${v}" ${current.vendors.includes(v) ? 'selected' : ''}>${v}</option>`
        ).join('')}
      </select>
      <select id="filter-model">
        <option value="">All Models</option>
        ${filters.models.map(m =>
          `<option value="${m}" ${current.models.includes(m) ? 'selected' : ''}>${m}</option>`
        ).join('')}
      </select>
    </div>
  `;

  for (const [id, key] of [['filter-agent', 'agents'], ['filter-vendor', 'vendors'], ['filter-model', 'models']]) {
    container.querySelector('#' + id).addEventListener('change', (e) => {
      const val = e.target.value;
      setFilter(key, val ? [val] : []);
    });
  }
}
