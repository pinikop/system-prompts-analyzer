export function renderSortableTable(container, { columns, rows, onRowClick }) {
  let sortCol = columns[0]?.key;
  let sortDir = 'asc';

  function render() {
    let displayRows = [...rows];
    if (sortCol) {
      displayRows.sort((a, b) => {
        const av = a[sortCol], bv = b[sortCol];
        const cmp = typeof av === 'number' ? av - bv : String(av).localeCompare(String(bv));
        return sortDir === 'asc' ? cmp : -cmp;
      });
    }

    const thead = columns.map(c => {
      const cls = c.key === sortCol ? `sortable sort-${sortDir}` : 'sortable';
      return `<th class="${cls}" data-col="${c.key}">${c.label}</th>`;
    }).join('');

    // Alternate group colors for multi-row agents, add border between groups
    const agentCounts = {};
    for (const row of displayRows) {
      if (row._agentId) agentCounts[row._agentId] = (agentCounts[row._agentId] || 0) + 1;
    }
    let groupColorIdx = 0;
    const groupColors = ['group-a', 'group-b'];
    const agentColorMap = {};
    const tbody = displayRows.map((row, i) => {
      const prev = displayRows[i - 1];
      const isNewGroup = !prev || prev._agentId !== row._agentId;
      if (isNewGroup && row._agentId && agentCounts[row._agentId] > 1) {
        agentColorMap[row._agentId] = groupColors[groupColorIdx % 2];
        groupColorIdx++;
      }
      const classes = [];
      if (isNewGroup && i > 0) classes.push('group-border');
      if (agentColorMap[row._agentId]) classes.push(agentColorMap[row._agentId]);
      const cells = columns.map(c => `<td>${row[c.key] ?? ''}</td>`).join('');
      return `<tr class="${classes.join(' ')}" data-idx="${i}">${cells}</tr>`;
    }).join('');

    container.innerHTML = `
      <figure>
        <table role="grid">
          <thead><tr>${thead}</tr></thead>
          <tbody>${tbody}</tbody>
        </table>
      </figure>
    `;

    container.querySelectorAll('th.sortable').forEach(th => {
      th.addEventListener('click', () => {
        const col = th.dataset.col;
        if (col === sortCol) { sortDir = sortDir === 'asc' ? 'desc' : 'asc'; }
        else { sortCol = col; sortDir = 'asc'; }
        render();
      });
    });

    if (onRowClick) {
      container.querySelectorAll('tbody tr').forEach(tr => {
        tr.style.cursor = 'pointer';
        tr.addEventListener('click', () => onRowClick(displayRows[parseInt(tr.dataset.idx)]));
      });
    }
  }

  render();
}
