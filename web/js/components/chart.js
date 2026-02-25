let _charts = {};

export function destroyChart(id) {
  if (_charts[id]) { _charts[id].destroy(); delete _charts[id]; }
}

export function createBarChart(canvasId, labels, datasets, options = {}) {
  destroyChart(canvasId);
  const ctx = document.getElementById(canvasId);
  if (!ctx) return null;
  _charts[canvasId] = new Chart(ctx, {
    type: 'bar',
    data: { labels, datasets },
    options: { responsive: true, maintainAspectRatio: false, ...options },
  });
  return _charts[canvasId];
}

export function createRadarChart(canvasId, labels, datasets, options = {}) {
  destroyChart(canvasId);
  const ctx = document.getElementById(canvasId);
  if (!ctx) return null;
  _charts[canvasId] = new Chart(ctx, {
    type: 'radar',
    data: { labels, datasets },
    options: { responsive: true, maintainAspectRatio: false, ...options },
  });
  return _charts[canvasId];
}

export function destroyAll() {
  Object.keys(_charts).forEach(destroyChart);
}
