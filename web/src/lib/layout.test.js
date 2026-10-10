import { describe, expect, it } from 'vitest';
import { layoutTier, panelWidths } from './layout.js';

describe('layout tiers', () => {
  it('maps common devices to the intended tier', () => {
    expect(layoutTier(375)).toBe('phone');
    expect(layoutTier(639)).toBe('phone');
    expect(layoutTier(768)).toBe('tablet');
    expect(layoutTier(1024)).toBe('laptop');
    expect(layoutTier(1366)).toBe('desktop');
    expect(layoutTier(2560)).toBe('desktop');
  });

  it('leaves the map at least a third of a laptop screen', () => {
    for (const width of [960, 1024, 1152, 1279]) {
      const { left, right } = panelWidths('laptop', width);
      expect(width - left - right).toBeGreaterThanOrEqual(width / 3 - 40);
    }
  });

  it('widens panels on very wide screens and has none on stacked tiers', () => {
    expect(panelWidths('desktop', 1920).left).toBeGreaterThan(panelWidths('desktop', 1366).left);
    expect(panelWidths('phone', 390)).toEqual({ left: 0, right: 0 });
  });
});
