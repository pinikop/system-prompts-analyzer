import { loadData } from './state.js';

const routes = {};
let currentCleanup = null;

export function registerRoute(pattern, handler) {
  routes[pattern] = handler;
}

function matchRoute(hash) {
  const path = (hash.replace(/^#/, '') || '/').split('?')[0];
  for (const [pattern, handler] of Object.entries(routes)) {
    const regex = new RegExp('^' + pattern.replace(/:(\w+)/g, '(?<$1>[^/]+)') + '$');
    const match = path.match(regex);
    if (match) return { handler, params: match.groups || {} };
  }
  return null;
}

function navigate() {
  if (currentCleanup) { currentCleanup(); currentCleanup = null; }
  const app = document.getElementById('app');
  const result = matchRoute(location.hash);
  if (result) {
    currentCleanup = result.handler(app, result.params) || null;
  } else {
    app.innerHTML = '<p>Page not found. <a href="#/">Go to dashboard</a></p>';
  }
}

async function init() {
  await loadData();
  const { renderDashboard } = await import('./views/dashboard.js');
  const { renderAgentDetail } = await import('./views/agent-detail.js');
  const { renderCompare } = await import('./views/compare.js');

  registerRoute('/', renderDashboard);
  registerRoute('/agent/:id', renderAgentDetail);
  registerRoute('/compare', renderCompare);

  window.addEventListener('hashchange', navigate);
  navigate();
}

init();
