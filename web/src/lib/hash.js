const SAFE = /^[A-Za-z0-9.\-]{1,64}$/;
const MAX_ITEMS = 200;

function list(value) {
  return String(value ?? '')
    .split(',')
    .map((v) => v.trim())
    .filter((v) => SAFE.test(v))
    .slice(0, MAX_ITEMS);
}

export function readHash(hash) {
  const params = new URLSearchParams(String(hash ?? '').replace(/^#/, ''));
  const actor = params.get('a');
  const mode = params.get('m');
  return {
    techniques: list(params.get('q')).map((t) => t.toUpperCase()),
    noise: list(params.get('n')).map((t) => t.toUpperCase()),
    actor: actor && SAFE.test(actor) ? actor : null,
    mode: ['observe', 'explore', 'trust'].includes(mode) ? mode : null
  };
}

export function writeHash({ techniques = [], noise = [], actor = null, mode = null }) {
  const params = new URLSearchParams();
  if (mode && mode !== 'observe') params.set('m', mode);
  if (techniques.length) params.set('q', techniques.join(','));
  if (noise.length) params.set('n', noise.join(','));
  if (actor) params.set('a', actor);
  const text = params.toString().replace(/%2C/g, ',');
  return text ? `#${text}` : '';
}
