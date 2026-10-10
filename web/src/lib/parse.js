const SEPARATORS = /[\s,;|]+/;
const TECHNIQUE = /^T\d{4}(\.\d{3})?$/;

export function isTechniqueId(token) {
  return TECHNIQUE.test(String(token).trim().toUpperCase());
}

export function rollUp(token) {
  return String(token).trim().toUpperCase().split('.')[0];
}

export function tokens(text) {
  return String(text ?? '')
    .split(SEPARATORS)
    .map((t) => t.trim())
    .filter(Boolean);
}

export function parseTechniques(text, vocabulary) {
  const known = [];
  const unknown = [];
  const seen = new Set();
  for (const raw of tokens(text)) {
    const upper = raw.toUpperCase();
    const id = isTechniqueId(upper) ? rollUp(upper) : upper;
    if (seen.has(id)) continue;
    seen.add(id);
    if (vocabulary.has(id)) known.push(id);
    else unknown.push(raw);
  }
  return { known, unknown };
}

export function looksLikeList(text) {
  const parts = tokens(text);
  return parts.length > 1 && parts.filter(isTechniqueId).length >= Math.ceil(parts.length / 2);
}
