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

    const tbody = displayRows.map((row, i) => {
      const prev = displayRows[i - 1];
      const isDup = prev && row._agentId && row._agentId === prev._agentId;
      const cls = isDup ? 'variant-row' : '';
      const cells = columns.map(c => `<td>${row[c.key] ?? ''}</td>`).join('');
      return `<tr class="${cls}" data-idx="${i}">${cells}</tr>`;
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
