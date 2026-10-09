<script>
  import { onMount, untrack } from 'svelte';
  import { prefersReducedMotion } from 'svelte/motion';
  import { select } from 'd3-selection';
  import 'd3-transition';
  import { zoom, zoomIdentity } from 'd3-zoom';
  import { easeCubicInOut } from 'd3-ease';
  import { station } from '../lib/station.svelte.js';
  import { fitTransform, paddedHull, smoothPath, toWorld, WORLD } from '../lib/geometry.js';
  import { pct } from '../lib/format.js';
  import { EMBLEM_BODY } from '../lib/brand.js';

  let { safe = { left: 0, right: 0, top: 0, bottom: 0 }, intro = false, hold = false, dim = false, controls = true } = $props();

  let width = $state(0);
  let height = $state(0);
  let svg;
  let sky;
  let camera = $state({ k: 1, x: 0, y: 0 });
  let settled = $state(false);
  let behaviour;

  const actors = $derived(
    (station.data?.actors ?? []).map((a) => {
      const [x, y] = toWorld(a.x, a.y);
      return { ...a, wx: x, wy: y, distance: Math.hypot(x, y), base: 2.2 + Math.sqrt(a.technique_count) * 0.42 };
    })
  );
  const worldById = $derived(new Map(actors.map((a) => [a.id, a])));

  const shapes = $derived(
    (station.data?.constellations ?? []).map((c) => {
      const points = c.members.map((id) => worldById.get(id)).filter(Boolean).map((a) => [a.wx, a.wy]);
      const hull = paddedHull(points, 16);
      return {
        id: c.id,
        label: c.label,
        size: c.size,
        path: hull ? smoothPath(hull) : null,
        segment: !hull && points.length === 2 ? points : null,
        anchor: points.length ? topOf(points) : [0, 0]
      };
    })
  );

  const field = $derived(station.result?.field ?? {});
  const topScore = $derived(station.result?.candidates?.[0]?.score ?? 0);
  const probe = $derived(station.result?.probe ? toWorld(station.result.probe.x, station.result.probe.y) : null);
  const beams = $derived(
    probe
      ? (station.result.candidates ?? []).slice(0, 5).map((c) => {
          const [x, y] = toWorld(c.x, c.y);
          const rel = topScore ? c.score / topScore : 0;
          return { id: c.id, rank: c.rank, name: c.name, x, y, rel };
        })
      : []
  );
  const resultStamp = $derived(
    station.result ? station.result.candidates.map((c) => c.id).slice(0, 5).join('|') + station.result.query.known.join(',') : ''
  );
  const ranked = $derived(new Map((station.result?.candidates ?? []).map((c) => [c.id, c.rank])));
  const labels = $derived(placeLabels(beams, camera.k));
  const hovered = $derived(station.hover ? worldById.get(station.hover) : null);
  const focused = $derived(station.dossierId ? worldById.get(station.dossierId) : null);
  const showClusterLabels = $derived(station.mode === 'explore');

  function placeLabels(items, scale) {
    const lineHeight = 16 / scale;
    const span = 130 / scale;
    const placed = [];
    for (const item of [...items].sort((a, b) => a.y - b.y || a.x - b.x)) {
      let y = item.y;
      for (const other of placed) {
        if (Math.abs(other.x - item.x) < span && Math.abs(other.ly - y) < lineHeight) y = other.ly + lineHeight;
      }
      placed.push({ ...item, ly: y });
    }
    return placed;
  }

  function topOf(points) {
    let best = points[0];
    for (const p of points) if (p[1] < best[1]) best = p;
    return best;
  }

  function glow(id) {
    const score = field[id];
    if (!score || !topScore) return 0;
    return Math.min(1, score / topScore);
  }

  function fly(target, duration = 1100) {
    if (!svg || !behaviour) return;
    const transform = zoomIdentity.translate(target.x, target.y).scale(target.k);
    const ms = prefersReducedMotion.current ? 0 : duration;
    select(svg).interrupt().transition().duration(ms).ease(easeCubicInOut).call(behaviour.transform, transform);
  }

  function fitAll(duration) {
    const points = actors.map((a) => [a.wx, a.wy]);
    fly(fitTransform(points, { width, height }, safe, { padding: 40, maxScale: 1.6 }), duration);
  }

  function fitPoints(points, options = {}) {
    fly(fitTransform(points, { width, height }, safe, { padding: 70, maxScale: 2.6, ...options }));
  }

  function fitResult(duration) {
    const points = beams.map((b) => [b.x, b.y]);
    if (probe) points.push(probe);
    fly(fitTransform(points, { width, height }, safe, { padding: 70, maxScale: 2.6 }), duration);
  }

  function screen(wx, wy) {
    return [wx * camera.k + camera.x, wy * camera.k + camera.y];
  }

  const dust = Array.from({ length: 460 }, (_, i) => {
    const r = (n) => {
      const v = Math.sin(i * 12.9898 + n * 78.233) * 43758.5453;
      return v - Math.floor(v);
    };
    return { x: r(1) * 3 - 1, y: r(2) * 3 - 1, size: 0.3 + r(3) * 1.1, alpha: 0.12 + r(4) * 0.5 };
  });

  let frame = 0;
  let drawn = '';

  function sizeSky() {
    if (!sky || !width || !height) return;
    const ratio = window.devicePixelRatio || 1;
    sky.width = Math.round(width * ratio);
    sky.height = Math.round(height * ratio);
    drawn = '';
    paintSky();
  }

  function paintSky() {
    if (!sky || !width || frame) return;
    frame = requestAnimationFrame(() => {
      frame = 0;
      const ox = Math.round((camera.x - width / 2) * 0.05);
      const oy = Math.round((camera.y - height / 2) * 0.05);
      const key = `${ox},${oy},${width},${height}`;
      if (key === drawn) return;
      drawn = key;
      const ratio = sky.width / width;
      const ctx = sky.getContext('2d');
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
      ctx.clearRect(0, 0, width, height);
      ctx.fillStyle = '#c9d4e3';
      for (const s of dust) {
        const x = (((s.x * width + ox) % (width * 2)) + width * 2) % (width * 2) - width * 0.5;
        const y = (((s.y * height + oy) % (height * 2)) + height * 2) % (height * 2) - height * 0.5;
        ctx.globalAlpha = s.alpha;
        ctx.fillRect(x, y, s.size, s.size);
      }
    });
  }

  onMount(() => {
    behaviour = zoom()
      .scaleExtent([0.3, 9])
      .on('zoom', (event) => {
        const { k, x, y } = event.transform;
        camera = { k, x, y };
      });
    select(svg).call(behaviour).on('dblclick.zoom', null);
    requestAnimationFrame(() => {
      fitAll(0);
      requestAnimationFrame(() => (settled = true));
    });
    return () => cancelAnimationFrame(frame);
  });

  $effect(() => {
    width;
    height;
    untrack(sizeSky);
  });

  $effect(() => {
    camera;
    untrack(paintSky);
  });

  $effect(() => {
    resultStamp;
    untrack(() => {
      if (!settled || station.dossierId) return;
      if (!station.result?.candidates?.length) fitAll(900);
      else fitResult(1100);
    });
  });

  $effect(() => {
    const target = focused;
    const ready = settled;
    untrack(() => {
      if (!ready || !target) return;
      fly(fitTransform([[target.wx, target.wy]], { width, height }, safe, { minSize: 260, maxScale: 2.4 }), 900);
    });
  });

  $effect(() => {
    const id = station.constellationFocus;
    untrack(() => {
      if (!settled || id === null) return;
      const c = station.constellations.get(id);
      if (!c) return;
      const points = c.members.map((m) => worldById.get(m)).filter(Boolean).map((a) => [a.wx, a.wy]);
      fitPoints(points, { minSize: 180, maxScale: 3 });
    });
  });

  $effect(() => {
    station.cameraRequest;
    untrack(() => settled && fitAll(900));
  });

  $effect(() => {
    safe.left;
    safe.right;
    width;
    height;
    untrack(() => {
      if (!settled) return;
      if (station.dossierId && focused) {
        fly(fitTransform([[focused.wx, focused.wy]], { width, height }, safe, { minSize: 260, maxScale: 2.4 }), 700);
      } else if (station.result?.candidates?.length) fitResult(800);
      else fitAll(700);
    });
  });

  function zoomBy(factor) {
    if (!svg || !behaviour) return;
    select(svg).transition().duration(prefersReducedMotion.current ? 0 : 380).call(behaviour.scaleBy, factor);
  }
</script>

<div class="map" class:dim class:intro bind:clientWidth={width} bind:clientHeight={height}>
  <canvas class="sky" bind:this={sky} aria-hidden="true"></canvas>

  <svg
    bind:this={svg}
    {width}
    {height}
    role="img"
    aria-label="Aktörlerin davranışsal benzerlik haritası. Yakın duran aktörler benzer teknikler kullanır."
    onpointerleave={() => (station.hover = null)}
  >
    <defs>
      <radialGradient id="halo">
        <stop offset="0%" stop-color="#ffb54a" stop-opacity="0.55" />
        <stop offset="60%" stop-color="#ff7b3a" stop-opacity="0.12" />
        <stop offset="100%" stop-color="#ff7b3a" stop-opacity="0" />
      </radialGradient>
      <radialGradient id="probe-core">
        <stop offset="0%" stop-color="#ffffff" />
        <stop offset="70%" stop-color="#ffe2b0" />
        <stop offset="100%" stop-color="#ffb54a" />
      </radialGradient>
    </defs>

    <g class="world" transform="translate({camera.x},{camera.y}) scale({camera.k})" style:--k={camera.k}>
      <g class="reticle">
        {#each [0.25, 0.5, 0.75, 1] as ring}
          <circle r={WORLD * ring} vector-effect="non-scaling-stroke" />
        {/each}
        <line x1={-WORLD * 1.08} x2={WORLD * 1.08} y1="0" y2="0" vector-effect="non-scaling-stroke" />
        <line y1={-WORLD * 1.08} y2={WORLD * 1.08} x1="0" x2="0" vector-effect="non-scaling-stroke" />
      </g>

      <g class="constellations" class:visible={settled && !hold}>
        {#each shapes as shape (shape.id)}
          {@const active = station.constellationFocus === shape.id}
          {#if shape.path}
            <path d={shape.path} class:active vector-effect="non-scaling-stroke" />
          {:else if shape.segment}
            <line
              x1={shape.segment[0][0]}
              y1={shape.segment[0][1]}
              x2={shape.segment[1][0]}
              y2={shape.segment[1][1]}
              class:active
              vector-effect="non-scaling-stroke"
            />
          {/if}
        {/each}
      </g>

      {#if probe}
        {#key resultStamp}
          <g class="beams">
            {#each beams as beam (beam.id)}
              <line
                x1={probe[0]}
                y1={probe[1]}
                x2={beam.x}
                y2={beam.y}
                pathLength="1"
                style:--w="{0.8 + beam.rel * 2.6}px"
                style:--delay="{beam.rank * 90}ms"
                style:opacity={0.25 + beam.rel * 0.75}
              />
            {/each}
          </g>
        {/key}
      {/if}

      <path class="hub" class:held={hold} d={EMBLEM_BODY} fill-rule="evenodd" transform="translate(-70 -70) scale(1.4)" />

      <g class="stars" class:held={hold}>
        {#each actors as actor (actor.id)}
          {@const g = glow(actor.id)}
          {@const rank = ranked.get(actor.id)}
          <g
            class="star"
            class:candidate={rank !== undefined && rank <= 5}
            class:focus={station.dossierId === actor.id || station.hover === actor.id}
            class:faded={station.constellationFocus !== null && actor.cluster !== station.constellationFocus}
            style:transform={(settled && !hold) || !intro ? `translate(${actor.wx}px, ${actor.wy}px)` : 'translate(0px, 0px)'}
            style:--delay="{intro ? Math.round(actor.distance * 1.6) : 0}ms"
            style:--r="{actor.base + g * 2.6}px"
            style:--hit="{Math.max(9, actor.base + 6)}px"
            style:--glow={g}
          >
            {#if g > 0.05}
              <circle class="halo" fill="url(#halo)" style:--h="{actor.base * 2 + g * 22}px" opacity={0.25 + g * 0.75} />
            {/if}
            <circle class="core" />
            <circle
              class="hit"
              role="presentation"
              onpointerenter={() => (station.hover = actor.id)}
              onclick={() => station.openDossier(actor.id)}
            />
          </g>
        {/each}
      </g>

      {#if probe}
        <g class="probe" transform="translate({probe[0]},{probe[1]})">
          {#key resultStamp}
            <circle class="ping" />
            <circle class="ping ping--late" />
          {/key}
          <circle class="probe-ring" vector-effect="non-scaling-stroke" />
          <circle class="probe-core" fill="url(#probe-core)" />
        </g>
      {/if}

      <g class="labels">
        {#if showClusterLabels}
          {#each shapes as shape (shape.id)}
            {#if shape.size >= 5 || station.constellationFocus === shape.id}
              <text class="cluster-label" x={shape.anchor[0]} y={shape.anchor[1]} dy="-1.8em" text-anchor="middle">
                {shape.label}
              </text>
            {/if}
          {/each}
        {/if}
        {#each labels as beam (beam.id)}
          <text class="candidate-label" x={beam.x} y={beam.ly} dx="1em" dy="0.34em">
            <tspan class="rank">{String(beam.rank).padStart(2, '0')}</tspan>
            {beam.name}
          </text>
        {/each}
        {#if focused && !ranked.has(focused.id)}
          <text class="candidate-label" x={focused.wx} y={focused.wy} dx="1em" dy="0.34em">{focused.name}</text>
        {/if}
      </g>
    </g>
  </svg>

  {#if hovered}
    {@const [sx, sy] = screen(hovered.wx, hovered.wy)}
    {@const constellation = station.constellations.get(hovered.cluster)}
    <div class="card" style:left="{sx}px" style:top="{sy}px" class:flip={sx > width - 300}>
      <div class="card-name">{hovered.name} <span class="mono">{hovered.id}</span></div>
      {#if hovered.aliases.length}
        <div class="card-alias">{hovered.aliases.slice(0, 3).join(' · ')}</div>
      {/if}
      <div class="card-meta mono">
        <span>{hovered.technique_count} teknik</span>
        {#if field[hovered.id]}<span class="hot">skor {field[hovered.id].toFixed(3)}</span>{/if}
        {#if ranked.has(hovered.id)}<span class="hot">#{ranked.get(hovered.id)}</span>{/if}
      </div>
      {#if constellation}
        <div class="card-cluster">{constellation.label}</div>
      {/if}
    </div>
  {/if}

  {#if controls}
    <div class="controls" style:right="{safe.right + 16}px" style:bottom="{safe.bottom + 16}px">
      <button class="ctl" onclick={() => zoomBy(1.4)} aria-label="Yakınlaştır">+</button>
      <button class="ctl" onclick={() => zoomBy(1 / 1.4)} aria-label="Uzaklaştır">−</button>
      <button class="ctl ctl--wide mono" onclick={() => station.recenter()} aria-label="Tüm haritayı göster">TÜMÜ</button>
    </div>
  {/if}

  {#if station.result?.candidates?.length}
    {@const room = width - safe.left - safe.right - 32}
    <div class="legend" style:left="{safe.left + 16}px" style:top="{safe.top + 12}px" style:max-width="{room}px">
      {#if room > 560}
        <span class="legend-probe"></span> gözlemin konumu
        <span class="legend-beam"></span> en yakın 5 aday · kalınlık = benzerlik
      {/if}
      <span class="mono legend-top">en yüksek {pct(topScore, 1)}</span>
    </div>
  {/if}
</div>

<style>
  .map {
    position: absolute;
    inset: 0;
    overflow: hidden;
    background:
      radial-gradient(1200px 800px at 50% 45%, rgba(40, 58, 86, 0.28), transparent 70%),
      var(--void);
    transition: filter var(--t-slow) var(--ease-out);
  }

  .map.dim {
    filter: saturate(0.5) brightness(0.45);
  }

  .sky {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    pointer-events: none;
  }

  svg {
    position: absolute;
    inset: 0;
    cursor: grab;
    touch-action: none;
  }

  svg:active {
    cursor: grabbing;
  }

  .reticle circle,
  .reticle line {
    fill: none;
    stroke: var(--seam);
    stroke-width: 1px;
    stroke-dasharray: 2 6;
    opacity: 0.7;
  }

  .constellations path,
  .constellations line {
    fill: rgba(111, 135, 168, 0.035);
    stroke: var(--seam-2);
    stroke-width: 1px;
    stroke-dasharray: 3 4;
    opacity: 0;
    transition: opacity var(--t-slow) var(--ease-out), stroke var(--t-base), fill var(--t-base);
  }

  .constellations.visible path,
  .constellations.visible line {
    opacity: 1;
    transition-delay: 900ms;
  }

  .constellations .active {
    stroke: var(--signal-line);
    fill: var(--signal-soft);
    stroke-dasharray: none;
  }

  .star {
    transition:
      transform var(--t-epic) var(--ease-out) var(--delay),
      opacity var(--t-slow) var(--ease-out);
  }

  .hub {
    fill: var(--ink);
    opacity: 0.035;
    pointer-events: none;
    transition: opacity 1200ms var(--ease-out) 600ms;
  }

  .hub.held {
    opacity: 0;
  }

  .stars.held {
    opacity: 0;
  }

  .stars {
    transition: opacity 400ms var(--ease-out);
  }

  .star.faded {
    opacity: 0.22;
  }

  .core {
    r: calc(var(--r) / var(--k));
    fill: color-mix(in oklab, #8fa0b8 calc((1 - var(--glow)) * 100%), #ffb54a);
    opacity: calc(0.62 + var(--glow) * 0.38);
  }

  .star.candidate .core {
    fill: #ffd08a;
  }

  .star.focus .core {
    fill: #ffffff;
    opacity: 1;
  }

  .halo {
    r: calc(var(--h) / var(--k));
    pointer-events: none;
  }

  .hit {
    r: calc(var(--hit) / var(--k));
    fill: transparent;
    cursor: pointer;
  }

  .beams line {
    stroke-width: calc(var(--w) / var(--k));
    stroke: var(--signal);
    stroke-linecap: round;
    stroke-dasharray: 1;
    stroke-dashoffset: 1;
    animation: draw 900ms var(--ease-out) var(--delay) forwards;
  }

  .probe-ring {
    r: calc(9px / var(--k));
    fill: none;
    stroke: var(--signal);
    stroke-width: 1.2px;
  }

  .probe-core {
    r: calc(4.2px / var(--k));
  }

  .ping {
    r: calc(26px / var(--k));
    fill: none;
    stroke: var(--signal);
    stroke-width: 1px;
    vector-effect: non-scaling-stroke;
    transform-box: fill-box;
    transform-origin: center;
    animation: ping 1600ms var(--ease-out) both;
  }

  .ping--late {
    animation-delay: 380ms;
  }

  .labels {
    font-size: calc(12px / var(--k));
  }

  .labels text {
    font-family: var(--sans);
    paint-order: stroke;
    stroke: var(--void);
    stroke-width: 3px;
    stroke-linejoin: round;
    vector-effect: non-scaling-stroke;
    pointer-events: none;
  }

  .candidate-label {
    fill: var(--ink);
    font-weight: 500;
  }

  .candidate-label .rank {
    font-family: var(--mono);
    fill: var(--signal);
  }

  .cluster-label {
    fill: var(--ink-3);
    font-size: 0.92em;
    letter-spacing: 0.02em;
  }

  .card {
    position: absolute;
    transform: translate(16px, -50%);
    min-width: 200px;
    max-width: 280px;
    padding: 10px 12px;
    background: rgba(10, 15, 23, 0.94);
    border: 1px solid var(--seam-2);
    pointer-events: none;
    animation: rise var(--t-fast) var(--ease-out) both;
    z-index: 5;
  }

  .card.flip {
    transform: translate(calc(-100% - 16px), -50%);
  }

  .card-name {
    font-weight: 600;
    font-size: 14px;
  }

  .card-name .mono {
    font-size: 12px;
    color: var(--ink-3);
    font-weight: 400;
    margin-left: 6px;
  }

  .card-alias {
    font-size: 12px;
    color: var(--ink-2);
    margin-top: 2px;
  }

  .card-meta {
    display: flex;
    gap: 10px;
    margin-top: 6px;
    font-size: 12px;
    color: var(--ink-3);
  }

  .card-meta .hot {
    color: var(--signal);
  }

  .card-cluster {
    margin-top: 6px;
    padding-top: 6px;
    border-top: 1px solid var(--seam);
    font-size: 12px;
    color: var(--ink-3);
  }

  .controls {
    position: absolute;
    display: flex;
    flex-direction: column;
    gap: 4px;
    transition: right var(--t-slow) var(--ease-out);
  }

  .ctl {
    width: 34px;
    height: 34px;
    border: 1px solid var(--seam-2);
    background: rgba(10, 15, 23, 0.85);
    color: var(--ink-2);
    font-size: 16px;
  }

  .ctl--wide {
    font-size: 9.5px;
    letter-spacing: 0.04em;
  }

  .ctl:hover {
    color: var(--ink);
    border-color: var(--seam-3);
  }

  .legend {
    position: absolute;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    color: var(--ink-3);
    padding: 6px 10px;
    background: rgba(4, 6, 10, 0.7);
    animation: rise var(--t-slow) var(--ease-out) both;
  }

  .legend-probe {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #ffe2b0;
    box-shadow: 0 0 0 3px rgba(255, 181, 74, 0.35);
  }

  .legend-beam {
    width: 22px;
    height: 2px;
    background: var(--signal);
    margin-left: 10px;
  }

  .legend-top {
    color: var(--signal);
  }

  .legend-beam + .legend-top,
  .legend-beam ~ .legend-top {
    margin-left: 10px;
  }

  @media (pointer: coarse) {
    .ctl {
      width: 42px;
      height: 42px;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .beams line {
      animation: none;
      stroke-dashoffset: 0;
    }
  }

  @keyframes draw {
    to {
      stroke-dashoffset: 0;
    }
  }

  @keyframes ping {
    0% {
      transform: scale(0.15);
      opacity: 0.9;
    }
    100% {
      transform: scale(2.4);
      opacity: 0;
    }
  }

  @keyframes rise {
    from {
      opacity: 0;
      translate: 0 6px;
    }
  }
</style>
