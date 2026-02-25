import { getData } from '../state.js';
import { createRadarChart, destroyAll } from '../components/chart.js';

function computeAverages(prompts) {
  const n = prompts.length || 1;
  const sum = (key) => prompts.reduce((s, p) => s + (p.metrics[key] || 0), 0) / n;
  return {
    word_count: Math.round(sum('word_count')),
    section_count: Math.round(sum('section_count')),
    directive_count: Math.round(sum('directive_count')),
    example_count: Math.round(sum('example_count')),
    directive_density: Math.round(sum('directive_density') * 10) / 10,
  };
}

function metricsPanel(m) {
  return `<div class="grid">
    <div class="metric-card"><div class="value">${m.word_count}</div><div class="label">Words</div></div>
    <div class="metric-card"><div class="value">${m.line_count}</div><div class="label">Lines</div></div>
    <div class="metric-card"><div class="value">${m.section_count}</div><div class="label">Sections</div></div>
    <div class="metric-card"><div class="value">${m.directive_count}</div><div class="label">Directives</div></div>
    <div class="metric-card"><div class="value">${m.directive_density}</div><div class="label">Dir/1K Words</div></div>
    <div class="metric-card"><div class="value">${m.example_count}</div><div class="label">Examples</div></div>
  </div>`;
}

function sectionBadges(m) {
  const cats = m.sections_by_category || {};
  return Object.entries(cats).map(([cat, count]) =>
    `<span class="category-badge ${cat}">${cat}: ${count}</span>`
  ).join(' ');
}

function toolsInfo(tools) {
  if (!tools.names.length) return '<p>No tools found.</p>';
  return `<p><strong>${tools.count} tools</strong>
    (${Object.entries(tools.sources || {}).map(([k, v]) => `${v} ${k}`).join(', ')})</p>
    <details><summary>Tool list</summary>
      <ul>${tools.names.map(n => `<li>${n}</li>`).join('')}</ul>
    </details>
    ${Object.keys(tools.categories || {}).length ? `
      <details><summary>Categories</summary>
        <ul>${Object.entries(tools.categories).map(([cat, names]) =>
          `<li><strong>${cat}:</strong> ${names.join(', ')}</li>`
        ).join('')}</ul>
      </details>` : ''}`;
}

export function renderAgentDetail(app, { id }) {
  const data = getData();
  const agentPrompts = data.prompts.filter(p => p.agent_id === id);
  if (!agentPrompts.length) {
    app.innerHTML = `<p>Agent "${id}" not found. <a href="#/">Back</a></p>`;
    return;
  }

  const agent = agentPrompts[0];
  const averages = computeAverages(data.prompts);

  app.innerHTML = `
    <nav aria-label="breadcrumb"><ul><li><a href="#/">Dashboard</a></li><li>${agent.agent_name}</li></ul></nav>
    <hgroup><h2>${agent.agent_name}</h2><p>${agent.vendor} - ${agentPrompts.length} variant(s)</p></hgroup>
    <div id="tab-bar">${agentPrompts.map((p, i) => `
      <button role="tab" class="outline ${i === 0 ? 'contrast' : 'secondary'}" data-idx="${i}">
        ${p.label}${p.model ? ` (${p.model})` : ''}
      </button>`).join(' ')}</div>
    <div id="variant-content"></div>
    <h3>Radar: This Agent vs Average</h3>
    <div class="chart-container" style="height:350px"><canvas id="radar-chart"></canvas></div>
  `;

  function showVariant(idx) {
    const p = agentPrompts[idx];
    document.getElementById('variant-content').innerHTML = `
      <article>
        <header><strong>${p.label}</strong>${p.model ? ` - Model: ${p.model}` : ''} ${p.is_latest ? '(latest)' : ''}</header>
        ${metricsPanel(p.metrics)}
        <h4>Sections</h4>${sectionBadges(p.metrics)}
        <h4>Tools</h4>${toolsInfo(p.tools)}
        <h4>Top Directives</h4>
        <ul>${Object.entries(p.metrics.directive_keywords || {})
          .sort(([,a],[,b]) => b - a).slice(0, 5)
          .map(([kw, count]) => `<li><strong>${kw}</strong>: ${count}</li>`).join('')}</ul>
      </article>`;
    app.querySelectorAll('[role="tab"]').forEach((btn, i) => {
      btn.className = `outline ${i === idx ? 'contrast' : 'secondary'}`;
    });
  }

  app.querySelectorAll('[role="tab"]').forEach(btn => {
    btn.addEventListener('click', () => showVariant(parseInt(btn.dataset.idx)));
  });
  showVariant(0);

  const latest = agentPrompts.find(p => p.is_latest) || agentPrompts[0];
  const radarLabels = ['Words/100', 'Sections', 'Directives', 'Dir Density', 'Examples', 'Tools'];
  createRadarChart('radar-chart', radarLabels, [
    {
      label: agent.agent_name,
      data: [latest.metrics.word_count/100, latest.metrics.section_count, latest.metrics.directive_count,
             latest.metrics.directive_density, latest.metrics.example_count, latest.tools.count],
      borderColor: '#3b82f6', backgroundColor: 'rgba(59,130,246,0.1)',
    },
    {
      label: 'Average',
      data: [averages.word_count/100, averages.section_count, averages.directive_count,
             averages.directive_density, averages.example_count,
             Math.round(data.prompts.reduce((s,p) => s + p.tools.count, 0) / data.prompts.length)],
      borderColor: '#6b7280', backgroundColor: 'rgba(107,114,128,0.1)',
    },
  ]);

  return () => destroyAll();
}
