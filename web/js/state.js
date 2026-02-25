let _data = null;
let _filters = { agents: [], vendors: [], models: [] };
let _listeners = [];

export async function loadData() {
  const resp = await fetch('data/analysis.json');
  _data = await resp.json();
  _notify();
  return _data;
}

export function getData() { return _data; }
export function getFilters() { return { ..._filters }; }

export function setFilter(key, values) {
  _filters[key] = values;
  _notify();
}

export function getFilteredPrompts() {
  if (!_data) return [];
  return _data.prompts.filter(p => {
    if (_filters.agents.length && !_filters.agents.includes(p.agent_id)) return false;
    if (_filters.vendors.length && !_filters.vendors.includes(p.vendor)) return false;
    if (_filters.models.length && !_filters.models.includes(p.model)) return false;
    return true;
  });
}

export function subscribe(fn) {
  _listeners.push(fn);
  return () => { _listeners = _listeners.filter(l => l !== fn); };
}

function _notify() { _listeners.forEach(fn => fn()); }
