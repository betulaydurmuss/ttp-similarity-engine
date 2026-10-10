import { describe, expect, it } from 'vitest';
import { isTechniqueId, looksLikeList, parseTechniques, rollUp, tokens } from './parse.js';

const vocabulary = new Set(['T1566', 'T1059', 'T1078']);

describe('parse', () => {
  it('splits on whitespace, commas, semicolons and pipes', () => {
    expect(tokens('T1566, T1059;T1078 | T1003\nT1105')).toEqual(['T1566', 'T1059', 'T1078', 'T1003', 'T1105']);
    expect(tokens('')).toEqual([]);
    expect(tokens(null)).toEqual([]);
  });

  it('recognises technique and sub-technique ids', () => {
    expect(isTechniqueId('T1566')).toBe(true);
    expect(isTechniqueId('t1059.001')).toBe(true);
    expect(isTechniqueId('T15')).toBe(false);
    expect(isTechniqueId('phishing')).toBe(false);
  });

  it('rolls sub-techniques up to the parent', () => {
    expect(rollUp('t1059.003')).toBe('T1059');
    expect(rollUp('T1566')).toBe('T1566');
  });

  it('keeps vocabulary hits in order, de-duplicated, and reports the rest', () => {
    const { known, unknown } = parseTechniques('T1078 t1566.002 T1566 T9999 foo T1059', vocabulary);
    expect(known).toEqual(['T1078', 'T1566', 'T1059']);
    expect(unknown).toEqual(['T9999', 'foo']);
  });

  it('treats a blob as a list only when most tokens are ids', () => {
    expect(looksLikeList('T1566 T1059')).toBe(true);
    expect(looksLikeList('T1566')).toBe(false);
    expect(looksLikeList('credential dumping tools')).toBe(false);
  });
});
