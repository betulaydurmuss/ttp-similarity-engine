const integer = new Intl.NumberFormat('tr-TR', { maximumFractionDigits: 0 });

export function int(value) {
  return integer.format(Math.round(Number(value) || 0));
}

export function dec(value, digits = 2) {
  return (Number(value) || 0).toFixed(digits).replace('.', ',');
}

export function pct(value, digits = 0) {
  return `%${dec((Number(value) || 0) * 100, digits)}`;
}

const HEAT_STOPS = [
  [0, [75, 95, 124]],
  [0.45, [154, 170, 191]],
  [0.78, [255, 181, 74]],
  [1, [255, 123, 58]]
];

export function heatColor(heat) {
  const h = Math.min(1, Math.max(0, Number(heat) || 0));
  for (let i = 1; i < HEAT_STOPS.length; i += 1) {
    const [stop, rgb] = HEAT_STOPS[i];
    const [prevStop, prevRgb] = HEAT_STOPS[i - 1];
    if (h <= stop) {
      const t = (h - prevStop) / (stop - prevStop);
      const mix = prevRgb.map((c, k) => Math.round(c + (rgb[k] - c) * t));
      return `rgb(${mix[0]}, ${mix[1]}, ${mix[2]})`;
    }
  }
  const last = HEAT_STOPS[HEAT_STOPS.length - 1][1];
  return `rgb(${last[0]}, ${last[1]}, ${last[2]})`;
}

export const DISTINCTIVE_SHARE = 0.05;
export const COMMON_SHARE = 0.35;

export function band(actorCount, totalActors) {
  const share = totalActors ? actorCount / totalActors : 0;
  if (share <= DISTINCTIVE_SHARE) return 'distinctive';
  if (share >= COMMON_SHARE) return 'common';
  return 'middle';
}

export const BAND_LABELS = {
  distinctive: 'ayırt edici',
  middle: 'orta',
  common: 'yaygın'
};

export const LEVELS = {
  high: { label: 'YÜKSEK', word: 'yüksek' },
  medium: { label: 'ORTA', word: 'orta' },
  low: { label: 'DÜŞÜK', word: 'düşük' }
};
