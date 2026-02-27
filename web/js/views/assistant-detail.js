import { getData, getAllPromptsForAssistant } from '../state.js';
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

const SAFETY_COLORS = { low: '#6b7280', medium: '#f59e0b', high: '#f97316', very_high: '#ef4444' };
const AUTONOMY_COLORS = { low: '#6b7280', medium: '#3b82f6', high: '#10b981' };

function llmAnalysisPanel(analysis) {
  if (!analysis) return '';
  const toneBadges = analysis.tone.map(t =>
    `<span class="category-badge tone">${t}</span>`
  ).join(' ');
  const safetyColor = SAFETY_COLORS[analysis.safety_emphasis] || '#6b7280';
  const autonomyColor = AUTONOMY_COLORS[analysis.autonomy_level] || '#6b7280';
  const safetyLabel = analysis.safety_emphasis.replace('_', ' ');

  return `
    <h4>LLM Analysis</h4>
    <article>
      <p><strong>Identity:</strong> ${analysis.identity}</p>
      <p><strong>Tone:</strong> ${toneBadges}</p>
      <p><strong>Personality:</strong> ${analysis.personality}</p>
      <p><strong>Coding Philosophy:</strong> ${analysis.coding_philosophy}</p>
      <p>
        <span class="category-badge" style="background:${safetyColor}">Safety: ${safetyLabel}</span>
        <span class="category-badge" style="background:${autonomyColor}">Autonomy: ${analysis.autonomy_level}</span>
      </p>
      <p><strong>Safety Details:</strong> ${analysis.safety_details}</p>
      <p><strong>Error Handling:</strong> ${analysis.error_handling}</p>
      <details><summary>Behavioral Rules (${analysis.behavioral_rules.length})</summary>
        <ul>${analysis.behavioral_rules.map(r => `<li>${r}</li>`).join('')}</ul>
      </details>
      <details><summary>Unique Features (${analysis.unique_features.length})</summary>
        <ul>${analysis.unique_features.map(f => `<li>${f}</li>`).join('')}</ul>
      </details>
    </article>`;
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

export function renderAssistantDetail(app, { id }) {
  const data = getData();
  const assistantPrompts = getAllPromptsForAssistant(id);
  if (!assistantPrompts.length) {
    app.innerHTML = `<p>Assistant "${id}" not found. <a href="#/">Back</a></p>`;
    return;
  }

  const assistant = assistantPrompts[0];
  const averages = computeAverages(data.prompts);

  app.innerHTML = `
    <nav aria-label="breadcrumb"><ul><li><a href="#/">Dashboard</a></li><li>${assistant.assistant_name}</li></ul></nav>
    <hgroup><h2>${assistant.vendor} / ${assistant.assistant_name}</h2><p>${assistantPrompts.length} variant(s)</p></hgroup>
    <div id="tab-bar">${assistantPrompts.map((p, i) => `
      <button role="tab" class="outline ${i === 0 ? 'contrast' : 'secondary'}" data-idx="${i}">
        ${p.label}${p.model ? ` (${p.model})` : ''}
      </button>`).join(' ')}</div>
    <div id="variant-content"></div>
    <h3>Radar: This Assistant vs Average</h3>
    <div class="chart-container" style="height:350px"><canvas id="radar-chart"></canvas></div>
  `;

  function showVariant(idx) {
    const p = assistantPrompts[idx];
    document.getElementById('variant-content').innerHTML = `
      <article>
        <header><strong>${p.label}</strong>${p.model ? ` - Model: ${p.model}` : ''} ${p.is_current ? '(current)' : ''}</header>
        ${metricsPanel(p.metrics)}
        <h4>Sections</h4>${sectionBadges(p.metrics)}
        <h4>Tools</h4>${toolsInfo(p.tools)}
        <h4>Top Directives</h4>
        <ul>${Object.entries(p.metrics.directive_keywords || {})
          .sort(([,a],[,b]) => b - a).slice(0, 5)
          .map(([kw, count]) => `<li><strong>${kw}</strong>: ${count}</li>`).join('')}</ul>
        ${llmAnalysisPanel(p.llm_analysis)}
      </article>`;
    app.querySelectorAll('[role="tab"]').forEach((btn, i) => {
      btn.className = `outline ${i === idx ? 'contrast' : 'secondary'}`;
    });
  }

  app.querySelectorAll('[role="tab"]').forEach(btn => {
    btn.addEventListener('click', () => showVariant(parseInt(btn.dataset.idx)));
  });
  showVariant(0);

  const latest = assistantPrompts.find(p => p.is_current) || assistantPrompts[0];
  const radarLabels = ['Words/100', 'Sections', 'Directives', 'Dir Density', 'Examples', 'Tools'];
  createRadarChart('radar-chart', radarLabels, [
    {
      label: assistant.assistant_name,
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
