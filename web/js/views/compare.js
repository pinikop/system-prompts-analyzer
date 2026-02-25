import { getData } from '../state.js';
import { createRadarChart, destroyAll } from '../components/chart.js';

function promptKey(p) { return `${p.agent_id}::${p.label}`; }

function delta(a, b) {
  const diff = a - b;
  if (diff === 0) return `${a}`;
  return `${a} <small>(${diff > 0 ? '+' : ''}${diff})</small>`;
}

export function renderCompare(app) {
  const data = getData();
  const prompts = data.prompts;

  const hash = location.hash.replace('#/compare', '');
  const params = new URLSearchParams(hash.startsWith('?') ? hash : '');
  let keyA = params.get('a') || '';
  let keyB = params.get('b') || '';

  function render() {
    const options = prompts.map(p => {
      const k = promptKey(p);
      return `<option value="${k}">${p.agent_name} - ${p.label}</option>`;
    }).join('');

    app.innerHTML = `
      <h2>Compare Prompts</h2>
      <div class="grid">
        <select id="sel-a"><option value="">Select prompt A</option>${options}</select>
        <select id="sel-b"><option value="">Select prompt B</option>${options}</select>
      </div>
      <div id="compare-content"></div>
    `;

    document.getElementById('sel-a').value = keyA;
    document.getElementById('sel-b').value = keyB;

    document.getElementById('sel-a').addEventListener('change', (e) => {
      keyA = e.target.value;
      location.hash = `#/compare?a=${encodeURIComponent(keyA)}&b=${encodeURIComponent(keyB)}`;
      renderComparison();
    });
    document.getElementById('sel-b').addEventListener('change', (e) => {
      keyB = e.target.value;
      location.hash = `#/compare?a=${encodeURIComponent(keyA)}&b=${encodeURIComponent(keyB)}`;
      renderComparison();
    });

    renderComparison();
  }

  function renderComparison() {
    const container = document.getElementById('compare-content');
    const pA = prompts.find(p => promptKey(p) === keyA);
    const pB = prompts.find(p => promptKey(p) === keyB);

    if (!pA || !pB) {
      container.innerHTML = '<p>Select two prompts to compare.</p>';
      return;
    }

    const mA = pA.metrics, mB = pB.metrics;
    const metrics = [
      ['Words', mA.word_count, mB.word_count],
      ['Lines', mA.line_count, mB.line_count],
      ['Sections', mA.section_count, mB.section_count],
      ['Directives', mA.directive_count, mB.directive_count],
      ['Dir. Density', mA.directive_density, mB.directive_density],
      ['Examples', mA.example_count, mB.example_count],
      ['Tools', pA.tools.count, pB.tools.count],
      ['Format', mA.format_type, mB.format_type],
    ];

    container.innerHTML = `
      <div class="compare-grid">
        <article><header><strong>${pA.agent_name}</strong> - ${pA.label}</header>
          <p>Vendor: ${pA.vendor} | Model: ${pA.model || '-'}</p></article>
        <article><header><strong>${pB.agent_name}</strong> - ${pB.label}</header>
          <p>Vendor: ${pB.vendor} | Model: ${pB.model || '-'}</p></article>
      </div>
      <figure><table>
        <thead><tr><th>Metric</th><th>${pA.agent_name}</th><th>${pB.agent_name}</th></tr></thead>
        <tbody>${metrics.map(([label, a, b]) => `<tr>
          <td>${label}</td>
          <td>${typeof a === 'number' ? delta(a, a-b) : a}</td>
          <td>${typeof b === 'number' ? delta(b, b-a) : b}</td>
        </tr>`).join('')}</tbody>
      </table></figure>
      <div class="chart-container" style="height:350px"><canvas id="compare-radar"></canvas></div>
    `;

    const labels = ['Words/100', 'Sections', 'Directives', 'Dir Density', 'Examples', 'Tools'];
    createRadarChart('compare-radar', labels, [
      {
        label: `${pA.agent_name} (${pA.label})`,
        data: [mA.word_count/100, mA.section_count, mA.directive_count, mA.directive_density, mA.example_count, pA.tools.count],
        borderColor: '#3b82f6', backgroundColor: 'rgba(59,130,246,0.1)',
      },
      {
        label: `${pB.agent_name} (${pB.label})`,
        data: [mB.word_count/100, mB.section_count, mB.directive_count, mB.directive_density, mB.example_count, pB.tools.count],
        borderColor: '#ef4444', backgroundColor: 'rgba(239,68,68,0.1)',
      },
    ]);
  }

  render();
  return () => destroyAll();
}
