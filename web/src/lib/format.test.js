import { describe, expect, it } from 'vitest';
import { band, dec, heatColor, int, pct } from './format.js';

describe('format', () => {
  it('uses Turkish number conventions', () => {
    expect(int(3667)).toBe('3.667');
    expect(dec(0.7439)).toBe('0,74');
    expect(pct(0.6843)).toBe('%68');
    expect(pct(0.6843, 1)).toBe('%68,4');
  });

  it('survives junk input', () => {
    expect(int(undefined)).toBe('0');
    expect(dec('x')).toBe('0,00');
  });

  it('maps heat onto the cold-to-hot ramp and clamps it', () => {
    expect(heatColor(0)).toBe('rgb(75, 95, 124)');
    expect(heatColor(1)).toBe('rgb(255, 123, 58)');
    expect(heatColor(-3)).toBe(heatColor(0));
    expect(heatColor(9)).toBe(heatColor(1));
    expect(heatColor(0.6)).not.toBe(heatColor(0.4));
  });

  it('bands techniques by how many actors use them', () => {
    expect(band(5, 149)).toBe('distinctive');
    expect(band(30, 149)).toBe('middle');
    expect(band(90, 149)).toBe('common');
    expect(band(1, 0)).toBe('distinctive');
  });
});
