import { polygonCentroid, polygonHull } from 'd3-polygon';

export const WORLD = 460;

export function toWorld(x, y) {
  return [x * WORLD, -y * WORLD];
}

export function bounds(points) {
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const [x, y] of points) {
    if (x < minX) minX = x;
    if (y < minY) minY = y;
    if (x > maxX) maxX = x;
    if (y > maxY) maxY = y;
  }
  return { minX, minY, maxX, maxY };
}

export function fitTransform(points, viewport, safe = {}, options = {}) {
  const { padding = 60, minSize = 120, maxScale = 3.2, minScale = 0.35 } = options;
  const left = safe.left ?? 0;
  const right = safe.right ?? 0;
  const top = safe.top ?? 0;
  const bottom = safe.bottom ?? 0;
  const availableW = Math.max(80, viewport.width - left - right - padding * 2);
  const availableH = Math.max(80, viewport.height - top - bottom - padding * 2);
  if (!points.length) {
    return { k: 1, x: left + (viewport.width - left - right) / 2, y: top + (viewport.height - top - bottom) / 2 };
  }
  const b = bounds(points);
  const w = Math.max(b.maxX - b.minX, minSize);
  const h = Math.max(b.maxY - b.minY, minSize);
  const k = Math.min(maxScale, Math.max(minScale, Math.min(availableW / w, availableH / h)));
  const cx = (b.minX + b.maxX) / 2;
  const cy = (b.minY + b.maxY) / 2;
  const screenCx = left + (viewport.width - left - right) / 2;
  const screenCy = top + (viewport.height - top - bottom) / 2;
  return { k, x: screenCx - cx * k, y: screenCy - cy * k };
}

export function paddedHull(points, pad = 18) {
  if (points.length < 3) return null;
  const hull = polygonHull(points);
  if (!hull) return null;
  const [cx, cy] = polygonCentroid(hull);
  return hull.map(([x, y]) => {
    const dx = x - cx;
    const dy = y - cy;
    const length = Math.hypot(dx, dy) || 1;
    return [x + (dx / length) * pad, y + (dy / length) * pad];
  });
}

export function smoothPath(polygon) {
  if (!polygon || polygon.length < 3) return '';
  const n = polygon.length;
  const mid = (a, b) => [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
  let d = '';
  for (let i = 0; i < n; i += 1) {
    const prev = polygon[(i - 1 + n) % n];
    const cur = polygon[i];
    const next = polygon[(i + 1) % n];
    const a = mid(prev, cur);
    const b = mid(cur, next);
    d += i === 0 ? `M${a[0].toFixed(1)},${a[1].toFixed(1)}` : '';
    d += `Q${cur[0].toFixed(1)},${cur[1].toFixed(1)} ${b[0].toFixed(1)},${b[1].toFixed(1)}`;
  }
  return `${d}Z`;
}

export function centroid(points) {
  const sum = points.reduce((acc, [x, y]) => [acc[0] + x, acc[1] + y], [0, 0]);
  return [sum[0] / points.length, sum[1] / points.length];
}
