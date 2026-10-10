export const BREAKPOINTS = { phone: 640, tablet: 960, laptop: 1280, wide: 1680 };

export function layoutTier(width) {
  if (width < BREAKPOINTS.phone) return 'phone';
  if (width < BREAKPOINTS.tablet) return 'tablet';
  if (width < BREAKPOINTS.laptop) return 'laptop';
  return 'desktop';
}

export function panelWidths(tier, width) {
  if (tier === 'laptop') {
    return { left: Math.round(Math.max(320, width * 0.29)), right: Math.round(Math.max(340, width * 0.31)) };
  }
  if (tier === 'desktop') {
    return width >= BREAKPOINTS.wide ? { left: 440, right: 470 } : { left: 404, right: 432 };
  }
  return { left: 0, right: 0 };
}
