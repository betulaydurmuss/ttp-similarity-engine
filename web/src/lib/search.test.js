import { describe, expect, it } from 'vitest';
import { matchedAlias, searchActors, searchTechniques } from './search.js';

const techniques = [
  { id: 'T1566', name: 'Phishing', heat: 0.2 },
  { id: 'T1534', name: 'Internal Spearphishing', heat: 0.9 },
  { id: 'T1003', name: 'OS Credential Dumping', heat: 0.3 },
  { id: 'T1556', name: 'Modify Authentication Process', heat: 0.6 },
  { id: 'T1059', name: 'Command and Scripting Interpreter', heat: 0.0 }
];

const actors = [
  { id: 'G0016', name: 'APT29', aliases: ['Cozy Bear', 'Midnight Blizzard'] },
  { id: 'G0032', name: 'Lazarus Group', aliases: ['HIDDEN COBRA'] },
  { id: 'G0065', name: 'Leviathan', aliases: ['APT40', 'MUDCARP'] }
];

describe('searchTechniques', () => {
  it('ranks an exact id first', () => {
    expect(searchTechniques(techniques, 't1566')[0].id).toBe('T1566');
  });

  it('matches id prefixes', () => {
    expect(searchTechniques(techniques, 'T15').map((t) => t.id)).toEqual(['T1534', 'T1556', 'T1566']);
  });

  it('matches name words and substrings, case-insensitively', () => {
    expect(searchTechniques(techniques, 'credential')[0].id).toBe('T1003');
    expect(searchTechniques(techniques, 'PHISH').map((t) => t.id)).toEqual(['T1566', 'T1534']);
  });

  it('folds Turkish dotted and dotless i', () => {
    expect(searchTechniques(techniques, 'İNTERNAL')[0].id).toBe('T1534');
    expect(searchTechniques(techniques, 'ınterpreter')[0].id).toBe('T1059');
  });

  it('requires all words for a multi-word query', () => {
    expect(searchTechniques(techniques, 'modify process').map((t) => t.id)).toEqual(['T1556']);
  });

  it('returns nothing for blank input and respects the limit', () => {
    expect(searchTechniques(techniques, '   ')).toEqual([]);
    expect(searchTechniques(techniques, 'T1', 2)).toHaveLength(2);
  });
});

describe('searchActors', () => {
  it('finds by id, name and alias', () => {
    expect(searchActors(actors, 'g0065')[0].id).toBe('G0065');
    expect(searchActors(actors, 'lazarus')[0].id).toBe('G0032');
    expect(searchActors(actors, 'apt40')[0].id).toBe('G0065');
  });

  it('reports which alias matched', () => {
    expect(matchedAlias(actors[2], 'mudcarp')).toBe('MUDCARP');
    expect(matchedAlias(actors[2], 'levi')).toBeNull();
  });
});
