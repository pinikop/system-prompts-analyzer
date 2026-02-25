import { getFilteredPrompts, getData, subscribe } from '../state.js';
import { renderFilterBar } from '../components/filter-bar.js';
import { createBarChart, destroyAll } from '../components/chart.js';
import { renderSortableTable } from '../components/table.js';

export function renderDashboard(app) {
  function render() {
    const prompts = getFilteredPrompts();
    const data = getData();

    app.innerHTML = `
      <h2>Dashboard</h2>
      <div id="filter-container"></div>
      <div class="grid">
        <div class="metric-card"><div class="value">${data.meta.agent_count}</div><div class="label">Agents</div></div>
        <div class="metric-card"><div class="value">${prompts.length}</div><div class="label">Prompts</div></div>
        <div class="metric-card"><div class="value">${data.filters.models.length}</div><div class="label">Models</div></div>
      </div>
      <div class="chart-container" style="height:300px"><canvas id="size-chart"></canvas></div>
      <div id="table-container"></div>
    `;

    renderFilterBar(document.getElementById('filter-container'));

    const labels = prompts.map(p => `${p.agent_name} (${p.label})`);
    const wordCounts = prompts.map(p => p.metrics.word_count);
    createBarChart('size-chart', labels, [{
      label: 'Word Count',
      data: wordCounts,
      backgroundColor: '#3b82f6',
    }]);

    const rows = prompts.map(p => ({
      agent: p.agent_name,
      label: p.label,
      model: p.model || '-',
      words: p.metrics.word_count,
      sections: p.metrics.section_count,
      tools: p.tools.count,
      directives: p.metrics.directive_count,
      format: p.metrics.format_type,
      _agentId: p.agent_id,
    }));

    renderSortableTable(document.getElementById('table-container'), {
      columns: [
        { key: 'agent', label: 'Agent' },
        { key: 'label', label: 'Variant' },
        { key: 'model', label: 'Model' },
        { key: 'words', label: 'Words' },
        { key: 'sections', label: 'Sections' },
        { key: 'tools', label: 'Tools' },
        { key: 'directives', label: 'Directives' },
        { key: 'format', label: 'Format' },
      ],
      rows,
      onRowClick: (row) => { location.hash = `#/agent/${row._agentId}`; },
    });
  }

  render();
  const unsub = subscribe(render);
  return () => { unsub(); destroyAll(); };
}
