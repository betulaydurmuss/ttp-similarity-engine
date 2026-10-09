<script>
  import { Tween, prefersReducedMotion } from 'svelte/motion';
  import { cubicOut } from 'svelte/easing';
  import { station } from '../lib/station.svelte.js';
  import { dec, pct, LEVELS } from '../lib/format.js';

  let { confidence } = $props();

  const SWEEP = 0.75;
  const START = 135;
  const rings = [
    { id: 'rarity', r: 69 },
    { id: 'margin', r: 59 },
    { id: 'sufficiency', r: 49 }
  ];

  const duration = () => (prefersReducedMotion.current ? 0 : 900);
  const values = {
    rarity: new Tween(0, { duration: duration(), easing: cubicOut }),
    margin: new Tween(0, { duration: duration(), easing: cubicOut, delay: 90 }),
    sufficiency: new Tween(0, { duration: duration(), easing: cubicOut, delay: 180 })
  };
  const total = new Tween(0, { duration: duration() + 200, easing: cubicOut });

  $effect(() => {
    for (const c of confidence.components) values[c.id].target = c.value;
    total.target = confidence.score;
  });

  const high = $derived(station.data?.scoring.high_threshold ?? 0.7);
  const medium = $derived(station.data?.scoring.medium_threshold ?? 0.45);
  const level = $derived(LEVELS[confidence.level] ?? LEVELS.low);

  function arc(r, fraction) {
    const length = 2 * Math.PI * r;
    return `${length * SWEEP * Math.max(0, Math.min(1, fraction))} ${length}`;
  }

  function tick(r, fraction) {
    const angle = ((START + 270 * fraction) * Math.PI) / 180;
    return {
      x1: 90 + (r - 5) * Math.cos(angle),
      y1: 90 + (r - 5) * Math.sin(angle),
      x2: 90 + (r + 5) * Math.cos(angle),
      y2: 90 + (r + 5) * Math.sin(angle)
    };
  }
</script>

<div class="dial level-{confidence.level}">
  <svg viewBox="0 0 180 180" width="172" height="172" role="img" aria-label="Güven {level.label}, skor {dec(confidence.score)}">
    <g transform="rotate({START} 90 90)">
      <circle class="track" cx="90" cy="90" r="80" stroke-dasharray={arc(80, 1)} />
      <circle class="total" cx="90" cy="90" r="80" stroke-dasharray={arc(80, total.current)} />
      {#each rings as ring}
        {@const component = confidence.components.find((c) => c.id === ring.id)}
        <circle class="track" cx="90" cy="90" r={ring.r} stroke-dasharray={arc(ring.r, 1)} />
        <circle
          class="value"
          class:weak={component?.weak}
          cx="90"
          cy="90"
          r={ring.r}
          stroke-dasharray={arc(ring.r, values[ring.id].current)}
        />
      {/each}
    </g>
    {#each [medium, high] as threshold}
      {@const t = tick(80, threshold)}
      <line class="threshold" {...t} />
    {/each}
    <text x="90" y="88" text-anchor="middle" class="lvl">{level.label}</text>
    <text x="90" y="106" text-anchor="middle" class="score">{dec(total.current)}</text>
  </svg>

  <ul class="legend">
    {#each confidence.components as c (c.id)}
      <li class:weak={c.weak} class:weakest={confidence.weakest === c.id}>
        <span class="swatch swatch-{c.id}"></span>
        <span class="name">{c.label} <em class="mono">×{dec(c.weight)}</em></span>
        <span class="mono val">{dec(c.value)}</span>
      </li>
    {/each}
    <li class="sum">
      <span class="swatch swatch-total"></span>
      <span class="name">Toplam</span>
      <span class="mono val">{dec(confidence.score)}</span>
    </li>
    <li class="thresholds mono">eşikler {dec(medium)} / {dec(high)}</li>
  </ul>
</div>

{#if confidence.reasons.length}
  <ul class="reasons">
    {#each confidence.reasons as reason}
      <li>{reason}</li>
    {/each}
  </ul>
{/if}

<style>
  .dial {
    display: grid;
    grid-template-columns: 172px 1fr;
    gap: 14px;
    align-items: center;
    --level: var(--danger);
  }

  .level-high {
    --level: var(--lock);
  }

  .level-medium {
    --level: var(--signal);
  }

  circle {
    fill: none;
    stroke-linecap: butt;
  }

  .track {
    stroke: var(--seam);
    stroke-width: 6;
  }

  .total {
    stroke: var(--level);
    stroke-width: 3;
  }

  .value {
    stroke: var(--ink-2);
    stroke-width: 6;
  }

  .value.weak {
    stroke: var(--danger);
  }

  circle.track:nth-of-type(1) {
    stroke-width: 3;
  }

  .threshold {
    stroke: var(--ink-3);
    stroke-width: 1.4;
  }

  .lvl {
    fill: var(--level);
    font-family: var(--sans);
    font-weight: 600;
    font-size: 12.5px;
    letter-spacing: 0.08em;
  }

  .score {
    fill: var(--ink);
    font-family: var(--mono);
    font-size: 14px;
  }

  .legend {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 6px;
  }

  .legend li {
    display: grid;
    grid-template-columns: 10px 1fr auto;
    gap: 8px;
    align-items: center;
    font-size: 13px;
    color: var(--ink-2);
  }

  .legend em {
    font-style: normal;
    font-size: 11.5px;
    color: var(--ink-3);
    margin-left: 4px;
  }

  .legend .val {
    color: var(--ink);
  }

  .legend li.weak .val,
  .legend li.weak .name {
    color: var(--danger);
  }

  .legend li.thresholds {
    display: block;
    font-size: 11.5px;
    color: var(--ink-3);
  }

  .legend li.sum {
    margin-top: 4px;
    padding-top: 7px;
    border-top: 1px solid var(--seam);
  }

  .swatch {
    width: 10px;
    height: 10px;
    background: var(--ink-2);
  }

  .swatch-margin {
    opacity: 0.8;
  }

  .swatch-sufficiency {
    opacity: 0.6;
  }

  .swatch-total {
    background: var(--level);
    height: 3px;
  }

  .reasons {
    list-style: none;
    margin: 12px 0 0;
    padding: 10px 12px;
    border-left: 2px solid var(--danger);
    background: rgba(255, 122, 107, 0.06);
    font-size: 13px;
    color: var(--ink-2);
  }

  .reasons li + li {
    margin-top: 4px;
  }

  @media (max-height: 820px) {
    .dial {
      grid-template-columns: 146px 1fr;
    }

    .dial svg {
      width: 146px;
      height: 146px;
    }
  }

  @media (max-width: 1180px) {
    .dial {
      grid-template-columns: 1fr;
      justify-items: center;
    }
    .legend {
      width: 100%;
    }
  }
</style>
