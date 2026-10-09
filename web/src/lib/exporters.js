import { heatColor, LEVELS, pct } from './format.js';

export function navigatorLayer({ result, techniques, dataset }) {
  const byId = new Map(techniques.map((t) => [t.id, t]));
  const top = result.candidates[0];
  const version = String(dataset.attack_version ?? '').split('.')[0] || undefined;
  return {
    name: top ? `Gözlem — en yakın: ${top.name}` : 'Gözlem',
    versions: { attack: version, navigator: '5.1.0', layer: '4.5' },
    domain: 'enterprise-attack',
    description:
      'TTP Benzerlik İstasyonu çıktısı. Skor = tekniğin nadirliği (0–1). Benzerlik ölçümüdür, faillik iddiası değildir.',
    techniques: result.query.known.map((id) => {
      const t = byId.get(id);
      const matched = top ? top.matched.includes(id) : false;
      return {
        techniqueID: id,
        score: Number((t?.heat ?? 0).toFixed(4)),
        color: heatColor(t?.heat ?? 0),
        comment: matched ? `${top.name} ile ortak` : 'en yakın adayda görülmedi',
        enabled: true,
        showSubtechniques: false
      };
    }),
    gradient: { colors: [heatColor(0), heatColor(1)], minValue: 0, maxValue: 1 },
    legendItems: [],
    metadata: [
      { name: 'veri seti', value: `MITRE ATT&CK v${dataset.attack_version ?? '?'}` },
      { name: 'güven', value: LEVELS[result.confidence.level]?.label ?? result.confidence.level }
    ],
    hideDisabled: false
  };
}

export function resultDocument({ result, dataset, generatedAt = new Date() }) {
  return {
    generated_at: generatedAt.toISOString(),
    dataset: { name: dataset.name, attack_version: dataset.attack_version },
    query: result.query,
    confidence: result.confidence,
    candidates: result.candidates.map(({ x, y, ...rest }) => rest),
    disclaimer: result.disclaimer
  };
}

export function markdownSummary({ result, dataset }) {
  const lines = [];
  const top = result.candidates[0];
  const level = LEVELS[result.confidence.level]?.label ?? result.confidence.level;
  lines.push(`## TTP benzerlik özeti — MITRE ATT&CK v${dataset.attack_version ?? '?'}`);
  lines.push('');
  lines.push(`**Gözlenen teknikler (${result.query.known.length}):** ${result.query.known.join(', ') || '—'}`);
  if (result.query.unknown.length) {
    lines.push(`**Tanınmayan girdiler:** ${result.query.unknown.join(', ')}`);
  }
  lines.push('');
  if (top) {
    lines.push(`Gözlenen davranış en çok **${top.name} (${top.id})** ile benzeşiyor. Güven: **${level}** (${result.confidence.score.toFixed(2)}).`);
    lines.push('');
    lines.push('| # | Aktör | Skor | Eşleşen |');
    lines.push('|---|---|---|---|');
    for (const c of result.candidates.slice(0, 5)) {
      lines.push(`| ${c.rank} | ${c.name} (${c.id}) | ${c.score.toFixed(3)} | ${c.matched.length}/${result.query.known.length} |`);
    }
    lines.push('');
    lines.push(`**Sonucu belirleyen teknikler:** ${top.evidence.slice(0, 5).map((e) => `${e.id} ${pct(e.share)}`).join(', ')}`);
  } else {
    lines.push('Bilinen tekniklerle eşleşen bir aktör bulunamadı.');
  }
  lines.push('');
  lines.push(`> ${result.disclaimer}`);
  return lines.join('\n');
}

export function download(filename, content, type = 'application/json') {
  const blob = new Blob([typeof content === 'string' ? content : JSON.stringify(content, null, 2)], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
