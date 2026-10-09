import { describe, expect, it } from 'vitest';
import { markdownSummary, navigatorLayer, resultDocument } from './exporters.js';

const dataset = { name: 'attck', attack_version: '19.2' };
const techniques = [
  { id: 'T1197', name: 'BITS Jobs', heat: 0.95 },
  { id: 'T1059', name: 'Command and Scripting Interpreter', heat: 0 }
];
const result = {
  query: { techniques: ['T1197', 'T1059', 'T9999'], known: ['T1197', 'T1059'], unknown: ['T9999'] },
  candidates: [
    {
      rank: 1, id: 'G0065', name: 'Leviathan', score: 0.63, matched: ['T1197'], missing: ['T1059'],
      evidence: [{ id: 'T1197', name: 'BITS Jobs', weight: 4.9, share: 1 }], x: 0.1, y: 0.2
    }
  ],
  confidence: { level: 'high', score: 0.74, components: [], reasons: [] },
  disclaimer: 'Benzerlik ölçümüdür, faillik değildir.'
};

describe('exporters', () => {
  it('builds a valid ATT&CK Navigator layer', () => {
    const layer = navigatorLayer({ result, techniques, dataset });
    expect(layer.domain).toBe('enterprise-attack');
    expect(layer.versions).toEqual({ attack: '19', navigator: '5.1.0', layer: '4.5' });
    expect(layer.techniques.map((t) => t.techniqueID)).toEqual(['T1197', 'T1059']);
    expect(layer.techniques[0].score).toBe(0.95);
    expect(layer.techniques[0].comment).toContain('Leviathan');
    expect(layer.techniques[1].comment).toContain('görülmedi');
    expect(layer.description).toContain('faillik');
  });

  it('drops map coordinates from the JSON document', () => {
    const doc = resultDocument({ result, dataset, generatedAt: new Date('2026-10-09T00:00:00Z') });
    expect(doc.generated_at).toBe('2026-10-09T00:00:00.000Z');
    expect(doc.candidates[0]).not.toHaveProperty('x');
    expect(doc.candidates[0].id).toBe('G0065');
    expect(doc.disclaimer).toBe(result.disclaimer);
  });

  it('writes a Markdown summary that keeps the disclaimer', () => {
    const md = markdownSummary({ result, dataset });
    expect(md).toContain('Leviathan (G0065)');
    expect(md).toContain('YÜKSEK');
    expect(md).toContain('T9999');
    expect(md).toContain('> Benzerlik ölçümüdür');
  });

  it('handles a result without candidates', () => {
    const md = markdownSummary({ result: { ...result, candidates: [] }, dataset });
    expect(md).toContain('eşleşen bir aktör bulunamadı');
    const layer = navigatorLayer({ result: { ...result, candidates: [] }, techniques, dataset });
    expect(layer.name).toBe('YILDIZ CTI · gözlem');
  });
});
