import { describe, expect, it } from 'vitest';
import { flightPlan } from './flight.js';

describe('flightPlan', () => {
  it('maps a source rectangle onto its landing rectangle', () => {
    const plan = flightPlan({ left: 500, top: 300, width: 400, height: 400 }, { left: 20, top: 16, width: 32, height: 32 });
    expect(plan).toEqual({ dx: -480, dy: -284, sx: 0.08, sy: 0.08 });
  });

  it('keeps aspect changes per axis', () => {
    const plan = flightPlan({ left: 0, top: 0, width: 200, height: 50 }, { left: 0, top: 0, width: 100, height: 50 });
    expect(plan.sx).toBe(0.5);
    expect(plan.sy).toBe(1);
  });

  it('never divides by zero', () => {
    expect(flightPlan({ left: 0, top: 0, width: 0, height: 0 }, { left: 1, top: 1, width: 1, height: 1 })).toEqual({ dx: 1, dy: 1, sx: 1, sy: 1 });
  });
});
