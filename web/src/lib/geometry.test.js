import { describe, expect, it } from 'vitest';
import { bounds, centroid, fitTransform, paddedHull, smoothPath, toWorld, WORLD } from './geometry.js';

describe('geometry', () => {
  it('maps layout space to world space with y pointing up', () => {
    expect(toWorld(1, 1)).toEqual([WORLD, -WORLD]);
    expect(toWorld(0, 0)).toEqual([0, -0]);
  });

  it('computes bounds and centroid', () => {
    const points = [[0, 0], [10, 4], [-2, 8]];
    expect(bounds(points)).toEqual({ minX: -2, minY: 0, maxX: 10, maxY: 8 });
    expect(centroid([[0, 0], [2, 2]])).toEqual([1, 1]);
  });

  it('centres the fitted points inside the safe area', () => {
    const points = [[-100, -50], [100, 50]];
    const viewport = { width: 1400, height: 900 };
    const safe = { left: 400, right: 400, top: 60, bottom: 0 };
    const t = fitTransform(points, viewport, safe, { padding: 50, maxScale: 10 });
    const cx = 0 * t.k + t.x;
    const cy = 0 * t.k + t.y;
    expect(cx).toBeCloseTo(400 + (1400 - 800) / 2);
    expect(cy).toBeCloseTo(60 + (900 - 60) / 2);
    const right = 100 * t.k + t.x;
    expect(right).toBeLessThanOrEqual(1400 - 400 - 50 + 1e-6);
  });

  it('clamps the zoom into its range', () => {
    const viewport = { width: 1000, height: 800 };
    expect(fitTransform([[0, 0]], viewport, {}, { maxScale: 2.5 }).k).toBeLessThanOrEqual(2.5);
    expect(fitTransform([[-1e6, 0], [1e6, 0]], viewport, {}, { minScale: 0.35 }).k).toBe(0.35);
  });

  it('falls back to the centre when there is nothing to fit', () => {
    const t = fitTransform([], { width: 800, height: 600 });
    expect(t).toEqual({ k: 1, x: 400, y: 300 });
  });

  it('pads a hull outward and draws a closed path', () => {
    expect(paddedHull([[0, 0], [1, 1]])).toBeNull();
    const square = [[0, 0], [10, 0], [10, 10], [0, 10]];
    const hull = paddedHull(square, 5);
    expect(hull).toHaveLength(4);
    for (const [x, y] of hull) {
      expect(Math.hypot(x - 5, y - 5)).toBeGreaterThan(Math.hypot(5, 5));
    }
    const path = smoothPath(hull);
    expect(path.startsWith('M')).toBe(true);
    expect(path.endsWith('Z')).toBe(true);
    expect(smoothPath(null)).toBe('');
  });
});
