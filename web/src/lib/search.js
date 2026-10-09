function fold(value) {
  return String(value ?? '')
    .toLocaleLowerCase('tr')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/ı/g, 'i');
}

function scoreTechnique(technique, needle, words) {
  const id = technique.id.toLowerCase();
  const name = fold(technique.name);
  if (id === needle) return 1000;
  if (id.startsWith(needle)) return 800 - id.length;
  if (needle.length < 2) return 0;
  if (name.startsWith(needle)) return 600;
  const nameWords = name.split(/[^a-z0-9]+/);
  if (nameWords.some((w) => w.startsWith(needle))) return 500;
  if (name.includes(needle)) return 400;
  if (words.length > 1 && words.every((w) => name.includes(w))) return 300;
  return 0;
}

export function searchTechniques(techniques, query, limit = 8) {
  const needle = fold(query).trim();
  if (!needle) return [];
  const words = needle.split(/\s+/).filter(Boolean);
  return techniques
    .map((t) => ({ t, s: scoreTechnique(t, needle, words) }))
    .filter((r) => r.s > 0)
    .sort((a, b) => b.s - a.s || b.t.heat - a.t.heat || a.t.id.localeCompare(b.t.id))
    .slice(0, limit)
    .map((r) => r.t);
}

export function searchActors(actors, query, limit = 8) {
  const needle = fold(query).trim();
  if (!needle) return [];
  return actors
    .map((a) => {
      const id = a.id.toLowerCase();
      const names = [a.name, ...a.aliases].map(fold);
      let s = 0;
      if (id === needle) s = 1000;
      else if (id.startsWith(needle)) s = 800;
      else if (names[0].startsWith(needle)) s = 700;
      else if (names.some((n) => n.startsWith(needle))) s = 600;
      else if (names.some((n) => n.includes(needle))) s = 400;
      return { a, s };
    })
    .filter((r) => r.s > 0)
    .sort((x, y) => y.s - x.s || x.a.name.localeCompare(y.a.name))
    .slice(0, limit)
    .map((r) => r.a);
}

export function matchedAlias(actor, query) {
  const needle = fold(query).trim();
  if (!needle || fold(actor.name).includes(needle)) return null;
  return actor.aliases.find((alias) => fold(alias).includes(needle)) ?? null;
}
