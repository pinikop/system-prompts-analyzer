export const SAFETY_COLORS = { low: '#6b7280', medium: '#f59e0b', high: '#f97316', very_high: '#ef4444' };
export const AUTONOMY_COLORS = { low: '#6b7280', medium: '#3b82f6', high: '#10b981' };
export const DEFAULT_BADGE_COLOR = '#6b7280';

export function safetyBadge(level) {
  if (!level) return '-';
  const color = SAFETY_COLORS[level] || DEFAULT_BADGE_COLOR;
  const label = level.replace('_', ' ');
  return `<span class="category-badge" style="background:${color}">${label}</span>`;
}

export function autonomyBadge(level) {
  if (!level) return '-';
  const color = AUTONOMY_COLORS[level] || DEFAULT_BADGE_COLOR;
  return `<span class="category-badge" style="background:${color}">${level}</span>`;
}
