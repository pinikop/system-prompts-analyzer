let _data = null;
let _filters = { assistants: [], models: [] };
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

export function toggleFilter(key, value) {
  const arr = _filters[key];
  const idx = arr.indexOf(value);
  if (idx === -1) {
    _filters[key] = [...arr, value];
  } else {
    _filters[key] = arr.filter(v => v !== value);
  }
  _notify();
}

/** Get latest prompts only, filtered. For dashboard use. */
export function getFilteredPrompts() {
  if (!_data) return [];
  return _data.prompts.filter(p => {
    if (!p.is_current) return false;
    if (_filters.assistants.length && !_filters.assistants.includes(p.assistant_id)) return false;
    if (_filters.models.length && !_filters.models.includes(p.model)) return false;
    return true;
  });
}

/** Get all prompts for an assistant (all versions). For detail view. */
export function getAllPromptsForAssistant(assistantId) {
  if (!_data) return [];
  return _data.prompts.filter(p => p.assistant_id === assistantId);
}

export function subscribe(fn) {
  _listeners.push(fn);
  return () => { _listeners = _listeners.filter(l => l !== fn); };
}

function _notify() { _listeners.forEach(fn => fn()); }
