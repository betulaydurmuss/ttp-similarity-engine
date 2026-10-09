import { describe, expect, it } from 'vitest';
import { readHash, writeHash } from './hash.js';

describe('hash state', () => {
  it('round-trips a full state', () => {
    const state = { techniques: ['T1566', 'T1078'], noise: ['T1059'], actor: 'G0065', mode: 'explore' };
    expect(readHash(writeHash(state))).toEqual(state);
  });

  it('omits defaults and keeps commas readable', () => {
    expect(writeHash({ techniques: ['T1566', 'T1078'] })).toBe('#q=T1566,T1078');
    expect(writeHash({})).toBe('');
    expect(writeHash({ mode: 'observe' })).toBe('');
  });

  it('upper-cases technique ids', () => {
    expect(readHash('#q=t1566,t1078').techniques).toEqual(['T1566', 'T1078']);
  });

  it('drops unsafe tokens instead of passing them through', () => {
    const state = readHash('#q=T1566,<script>,T1078&a=<img>&m=hack');
    expect(state.techniques).toEqual(['T1566', 'T1078']);
    expect(state.actor).toBeNull();
    expect(state.mode).toBeNull();
  });

  it('caps the number of techniques', () => {
    const many = Array.from({ length: 500 }, (_, i) => `T${1000 + i}`).join(',');
    expect(readHash(`#q=${many}`).techniques).toHaveLength(200);
  });

  it('handles an empty or missing hash', () => {
    expect(readHash('')).toEqual({ techniques: [], noise: [], actor: null, mode: null });
    expect(readHash(undefined).techniques).toEqual([]);
  });
});
