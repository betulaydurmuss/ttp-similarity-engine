export const LAND_EASING = 'cubic-bezier(0.65, 0, 0.35, 1)';

export function flightPlan(from, to) {
  return {
    dx: to.left - from.left,
    dy: to.top - from.top,
    sx: from.width ? to.width / from.width : 1,
    sy: from.height ? to.height / from.height : 1
  };
}

const FROZEN = ['opacity', 'fill', 'stroke', 'transform', 'filter', 'color'];

function freeze(source, clone) {
  const sources = [source, ...source.querySelectorAll('*')];
  const clones = [clone, ...clone.querySelectorAll('*')];
  sources.forEach((element, i) => {
    const style = getComputedStyle(element);
    const target = clones[i];
    for (const property of FROZEN) target.style.setProperty(property, style.getPropertyValue(property));
    target.style.setProperty('animation', 'none');
    target.style.setProperty('transition', 'none');
  });
}

export function flyElement(source, target, { duration = 900, easing = LAND_EASING, delay = 0 } = {}) {
  if (!source || !target) return Promise.resolve();
  const from = source.getBoundingClientRect();
  const to = target.getBoundingClientRect();
  if (!from.width || !to.width) return Promise.resolve();

  const clone = source.cloneNode(true);
  freeze(source, clone);
  const color = getComputedStyle(source).color;
  Object.assign(clone.style, {
    position: 'fixed',
    left: `${from.left}px`,
    top: `${from.top}px`,
    width: `${from.width}px`,
    height: `${from.height}px`,
    margin: '0',
    zIndex: '95',
    pointerEvents: 'none',
    transformOrigin: '0 0',
    color
  });
  document.body.appendChild(clone);
  source.style.visibility = 'hidden';
  target.style.visibility = 'hidden';

  const { dx, dy, sx, sy } = flightPlan(from, to);
  const animation = clone.animate(
    [
      { transform: 'translate(0px, 0px) scale(1, 1)' },
      { transform: `translate(${dx}px, ${dy}px) scale(${sx}, ${sy})` }
    ],
    { duration, easing, delay, fill: 'forwards' }
  );

  return animation.finished
    .catch(() => {})
    .then(() => {
      target.style.visibility = '';
      clone.remove();
    });
}

export function flyBrand(fromSlot, toSlot, options = {}) {
  if (!fromSlot || !toSlot) return Promise.resolve();
  const pairs = ['emblem', 'word'].map((part) => [
    fromSlot.querySelector(`[data-brand="${part}"]`),
    toSlot.querySelector(`[data-brand="${part}"]`)
  ]);
  return Promise.all(
    pairs.map(([source, target], i) => flyElement(source, target, { ...options, delay: (options.delay ?? 0) + i * 60 }))
  );
}
