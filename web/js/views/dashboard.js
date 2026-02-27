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
        <div class="metric-card"><div class="value">${new Set(prompts.map(p => p.assistant_id)).size}</div><div class="label">Assistants</div></div>
        <div class="metric-card"><div class="value">${prompts.length}</div><div class="label">Prompts</div></div>
        <div class="metric-card"><div class="value">${new Set(prompts.map(p => p.model).filter(Boolean)).size}</div><div class="label">Target Models</div></div>
      </div>
      <div class="chart-container" style="height:400px"><canvas id="size-chart"></canvas></div>
      <div id="table-container"></div>
    `;

    renderFilterBar(document.getElementById('filter-container'));

    const globalMax = Math.max(...data.prompts.map(p => p.metrics.word_count));
    const shortName = (name) => name.replace(/ Agent| Code|\(Copilot\)/g, '').trim();
    const labels = prompts.map(p => p.model ? `${shortName(p.assistant_name)} ${p.model}` : shortName(p.assistant_name));
    const wordCounts = prompts.map(p => p.metrics.word_count);
    createBarChart('size-chart', labels, [{
      label: 'Word Count',
      data: wordCounts,
      backgroundColor: '#3b82f6',
    }], {
      scales: {
        y: { beginAtZero: true, max: Math.ceil(globalMax / 1000) * 1000 },
        x: { ticks: { maxRotation: 45, minRotation: 25, font: { size: 11 } } },
      },
      plugins: { legend: { display: false } },
    });

    const safetyBadge = (level) => {
      if (!level) return '-';
      const colors = { low: '#6b7280', medium: '#f59e0b', high: '#f97316', very_high: '#ef4444' };
      const label = level.replace('_', ' ');
      return `<span class="category-badge" style="background:${colors[level] || '#6b7280'}">${label}</span>`;
    };
    const toneBadges = (tones) => {
      if (!tones) return '-';
      return tones.slice(0, 3).map(t =>
        `<span class="category-badge tone">${t}</span>`
      ).join(' ');
    };

    const rows = prompts.map(p => {
      const llm = p.llm_analysis;
      return {
        agent: p.assistant_name,
        label: p.label,
        model: p.model || '-',
        words: p.metrics.word_count,
        lines: p.metrics.line_count,
        sections: p.metrics.section_count,
        tools: p.tools.count,
        directives: p.metrics.directive_count,
        format: p.metrics.format_type,
        tone: llm ? toneBadges(llm.tone) : '-',
        safety: llm ? safetyBadge(llm.safety_emphasis) : '-',
        _assistantId: p.assistant_id,
        _safetyRaw: llm ? llm.safety_emphasis : '',
      };
    });

    renderSortableTable(document.getElementById('table-container'), {
      columns: [
        { key: 'agent', label: 'Assistant' },
        { key: 'label', label: 'Version' },
        { key: 'model', label: 'Target Model' },
        { key: 'words', label: 'Words' },
        { key: 'lines', label: 'Lines' },
        { key: 'sections', label: 'Sections' },
        { key: 'tools', label: 'Tools' },
        { key: 'directives', label: 'Directives' },
        { key: 'tone', label: 'Tone', html: true },
        { key: 'safety', label: 'Safety', html: true },
        { key: 'format', label: 'Format' },
      ],
      rows,
      onRowClick: (row) => { location.hash = `#/assistant/${row._assistantId}`; },
    });
  }

  render();
  const unsub = subscribe(render);
  return () => { unsub(); destroyAll(); };
}
