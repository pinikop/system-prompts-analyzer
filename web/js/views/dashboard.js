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
        <div class="metric-card"><div class="value">${new Set(prompts.map(p => p.agent_id)).size}</div><div class="label">Assistants</div></div>
        <div class="metric-card"><div class="value">${prompts.length}</div><div class="label">Prompts</div></div>
        <div class="metric-card"><div class="value">${new Set(prompts.map(p => p.model).filter(Boolean)).size}</div><div class="label">Target Models</div></div>
      </div>
      <div class="chart-container" style="height:300px"><canvas id="size-chart"></canvas></div>
      <div id="table-container"></div>
    `;

    renderFilterBar(document.getElementById('filter-container'));

    const globalMax = Math.max(...data.prompts.map(p => p.metrics.word_count));
    const shortName = (name) => name.replace(/ Agent| Code|\(Copilot\)/g, '').trim();
    const labels = prompts.map(p => p.model ? `${shortName(p.agent_name)} ${p.model}` : shortName(p.agent_name));
    const wordCounts = prompts.map(p => p.metrics.word_count);
    createBarChart('size-chart', labels, [{
      label: 'Word Count',
      data: wordCounts,
      backgroundColor: '#3b82f6',
    }], {
      scales: { y: { beginAtZero: true, max: Math.ceil(globalMax / 1000) * 1000 } },
    });

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
        { key: 'agent', label: 'Assistant' },
        { key: 'label', label: 'Version' },
        { key: 'model', label: 'Target Model' },
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
