<script>
  import { onMount } from 'svelte';
  import { EMBLEM_BODY, EMBLEM_STAR, STAR_CENTER, WORD_LETTERS, WORD_WIDTH } from '../../lib/brand.js';
  import { flyBrand } from '../../lib/flight.js';

  let { variant = 'full', ready = false, landing = () => null, onlanded } = $props();

  const pace = variant === 'full' ? 1 : variant === 'short' ? 0.55 : 0;
  const calm = variant === 'calm';
  const [sx, sy] = STAR_CENTER;
  const embers = Array.from({ length: 18 }, (_, i) => {
    const r = (n) => {
      const v = Math.sin((i + 1) * 91.17 + n * 47.3) * 10000;
      return v - Math.floor(v);
    };
    return { x: 18 + r(1) * 64, drift: (r(2) - 0.5) * 22, size: 0.5 + r(3) * 1.1, delay: r(4) * 1400, life: 1400 + r(5) * 1300 };
  });

  let armed = $state(false);
  let revealed = $state(false);
  let leaving = $state(false);
  let slot;
  let done = false;

  async function land() {
    if (done) return;
    done = true;
    leaving = true;
    const target = landing();
    await flyBrand(slot, target, { duration: calm ? 0 : Math.round(1050 * Math.max(pace, 0.7)) });
    onlanded?.();
  }

  function skip() {
    if (!armed) armed = true;
    revealed = true;
  }

  $effect(() => {
    if (revealed && ready) land();
  });

  onMount(() => {
    const arm = () => {
      if (document.visibilityState === 'visible') {
        armed = true;
        if (calm) setTimeout(() => (revealed = true), 650);
      }
    };
    const onKey = (event) => {
      if (['Escape', 'Enter', ' '].includes(event.key)) {
        event.preventDefault();
        skip();
      }
    };
    arm();
    document.addEventListener('visibilitychange', arm);
    window.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('visibilitychange', arm);
      window.removeEventListener('keydown', onKey);
    };
  });
</script>

<div
  class="ignition"
  class:armed
  class:calm
  class:revealed
  class:leaving
  style:--k={pace || 1}
  role="presentation"
  onclick={skip}
>
  <div class="ember-glow" aria-hidden="true"></div>

  <div class="stage">
    <div class="slot" bind:this={slot} role="img" aria-label="YILDIZ CTI">
      <span class="part emblem-part" data-brand="emblem">
        <svg class="mark" viewBox="0 0 100 100" aria-hidden="true">
          <path class="fill" d={EMBLEM_BODY} fill-rule="evenodd" />
          <path class="final-star" d={EMBLEM_STAR} />
        </svg>
      </span>
      <span class="part word-part" data-brand="word">
        <svg class="word" viewBox="0 0 {WORD_WIDTH} 100" aria-hidden="true">
          {#each WORD_LETTERS as letter, i}
            <path d={letter.d} fill-rule="evenodd" style:--i={i} />
          {/each}
        </svg>
      </span>
    </div>

    <svg class="fx" viewBox="-30 -30 160 160" aria-hidden="true">
      <defs>
        <radialGradient id="ig-spark">
          <stop offset="0%" stop-color="#ffffff" />
          <stop offset="35%" stop-color="#ffe2b0" />
          <stop offset="100%" stop-color="#ffb54a" stop-opacity="0" />
        </radialGradient>
        <radialGradient id="ig-fire" cx="50%" cy="60%" r="60%">
          <stop offset="0%" stop-color="#ffd08a" />
          <stop offset="55%" stop-color="#ff8a3d" />
          <stop offset="100%" stop-color="#ff4d2e" />
        </radialGradient>
        <linearGradient id="ig-flare" x1="0" x2="1">
          <stop offset="0%" stop-color="#ffb54a" stop-opacity="0" />
          <stop offset="50%" stop-color="#fff3dc" />
          <stop offset="100%" stop-color="#ffb54a" stop-opacity="0" />
        </linearGradient>
        <linearGradient id="ig-sheen" x1="0" x2="1" y1="0" y2="0.35">
          <stop offset="0%" stop-color="#ffffff" stop-opacity="0" />
          <stop offset="50%" stop-color="#ffffff" stop-opacity="0.85" />
          <stop offset="100%" stop-color="#ffffff" stop-opacity="0" />
        </linearGradient>
        <filter id="ig-flame" x="-40%" y="-40%" width="180%" height="180%" color-interpolation-filters="sRGB">
          <feTurbulence type="fractalNoise" baseFrequency="0.06" numOctaves="2" seed="7" result="noise">
            {#if !calm}
              <animate attributeName="baseFrequency" dur="0.9s" values="0.05;0.078;0.05" repeatCount="indefinite" />
            {/if}
          </feTurbulence>
          <feDisplacementMap in="SourceGraphic" in2="noise" scale="10" xChannelSelector="R" yChannelSelector="B" result="warp" />
          <feGaussianBlur in="warp" stdDeviation="1.6" result="soft" />
          <feMerge>
            <feMergeNode in="soft" />
            <feMergeNode in="warp" />
          </feMerge>
        </filter>
        <clipPath id="ig-body">
          <path d={EMBLEM_BODY} clip-rule="evenodd" fill-rule="evenodd" />
        </clipPath>
      </defs>

      <g class="orbits">
        <g class="spin">
          <circle class="ring" cx="50" cy="50" r="60" pathLength="1" />
          <circle class="satellite" cx="110" cy="50" r="1.6" />
        </g>
        <g class="spin-back">
          <circle class="ring-dash" cx="50" cy="50" r="68" />
        </g>
      </g>

      <path class="flame" d={EMBLEM_BODY} fill-rule="evenodd" fill="url(#ig-fire)" filter="url(#ig-flame)" />
      <path class="outline" d={EMBLEM_BODY} pathLength="1" />
      <g clip-path="url(#ig-body)">
        <rect class="sheen" x="-60" y="-10" width="46" height="130" fill="url(#ig-sheen)" />
      </g>

      <g class="embers">
        {#each embers as e}
          <circle
            cx={e.x}
            cy="88"
            r={e.size}
            style:--drift="{e.drift}px"
            style:--delay="{e.delay}ms"
            style:--life="{e.life}ms"
          />
        {/each}
      </g>

      <g class="star-group" style:transform-origin="{sx}px {sy}px">
        <g class="flares">
          {#each [[0, 68, 0.7, false], [90, 44, 0.7, false], [45, 28, 0.5, true], [-45, 28, 0.5, true]] as [angle, length, thick, diag]}
            <g transform="rotate({angle} {sx} {sy})">
              <rect class:diag x={sx - length / 2} y={sy - thick / 2} width={length} height={thick} fill="url(#ig-flare)" />
            </g>
          {/each}
        </g>
        <circle class="spark" cx={sx} cy={sy} r="5" fill="url(#ig-spark)" />
        <path class="star" d={EMBLEM_STAR} />
      </g>
    </svg>

    <p class="tagline mono" onanimationend={(event) => event.animationName.includes('rise') && (revealed = true)}>
      CTI · TTP BENZERLİK İSTASYONU
    </p>
    <p class="waiting mono" aria-live="polite">{revealed && !ready ? 'istasyon bağlanıyor…' : ''}</p>
  </div>

  <button class="skip mono" onclick={skip}>ATLA <span class="kbd">Esc</span></button>
</div>

<style>
  .ignition {
    --k: 1;
    position: fixed;
    inset: 0;
    z-index: 80;
    display: grid;
    place-items: center;
    background:
      radial-gradient(circle at 50% 44%, rgba(255, 140, 60, 0.08), transparent 46%),
      var(--void);
    cursor: pointer;
    transition: opacity calc(650ms * var(--k)) var(--ease-out);
  }

  .ignition.leaving {
    pointer-events: none;
    background: transparent;
  }

  .ignition.leaving .ember-glow,
  .ignition.leaving .fx,
  .ignition.leaving .tagline,
  .ignition.leaving .skip,
  .ignition.leaving .waiting {
    opacity: 0;
    transition: opacity 380ms var(--ease-out);
  }

  .ember-glow {
    position: absolute;
    width: min(90vmin, 860px);
    aspect-ratio: 1;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(255, 123, 58, 0.18), rgba(255, 123, 58, 0) 62%);
    opacity: 0;
    pointer-events: none;
  }

  .stage {
    --mark: clamp(200px, 44vmin, 420px);
    position: relative;
    display: grid;
    justify-items: center;
  }

  .slot {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: calc(var(--mark) * 0.1);
  }

  .part {
    display: block;
    color: var(--ink);
  }

  .mark {
    display: block;
    width: var(--mark);
    height: var(--mark);
    overflow: visible;
  }

  .word {
    display: block;
    width: calc(var(--mark) * 0.86);
    height: auto;
    overflow: hidden;
  }

  .fx {
    position: absolute;
    left: 50%;
    top: 0;
    width: calc(var(--mark) * 1.6);
    height: calc(var(--mark) * 1.6);
    margin-left: calc(var(--mark) * -0.8);
    margin-top: calc(var(--mark) * -0.3);
    overflow: visible;
    pointer-events: none;
  }

  .fill {
    fill: currentColor;
    opacity: 0;
  }

  .final-star {
    fill: var(--signal);
    opacity: 0;
  }

  .word path {
    fill: currentColor;
    transform-box: fill-box;
    transform: translateY(120%);
  }

  .ring,
  .ring-dash,
  .satellite,
  .flame,
  .outline,
  .sheen,
  .spark,
  .flares rect,
  .star,
  .embers circle,
  .tagline,
  .skip {
    opacity: 0;
  }

  .ring {
    fill: none;
    stroke: var(--seam-3);
    stroke-width: 0.45;
    stroke-dasharray: 1;
    stroke-dashoffset: 1;
  }

  .ring-dash {
    fill: none;
    stroke: var(--seam-2);
    stroke-width: 0.35;
    stroke-dasharray: 0.6 3.2;
  }

  .satellite {
    fill: var(--ink);
  }

  .spin {
    transform-origin: 50px 50px;
    animation: spin 14s linear infinite;
  }

  .spin-back {
    transform-origin: 50px 50px;
    animation: spin 22s linear infinite reverse;
  }

  .flame {
    transform-origin: 50px 52px;
  }

  .outline {
    fill: none;
    stroke: var(--ink);
    stroke-width: 0.5;
    stroke-linejoin: round;
    stroke-dasharray: 1;
    stroke-dashoffset: 1;
  }

  .sheen {
    transform: translateX(0) skewX(-14deg);
  }

  .star-group {
    transform-box: view-box;
  }

  .spark,
  .flares rect,
  .star {
    transform-box: fill-box;
    transform-origin: center;
  }

  .star {
    fill: var(--signal);
  }

  .embers circle {
    fill: #ffb067;
    transform-box: fill-box;
    transform-origin: center;
  }

  .tagline {
    margin: calc(var(--mark) * 0.08) 0 0;
    font-size: clamp(10.5px, 1.7vmin, 13px);
    letter-spacing: 0.34em;
    color: var(--ink-3);
  }

  .waiting {
    min-height: 1.4em;
    margin: 10px 0 0;
    font-size: 11.5px;
    letter-spacing: 0.16em;
    color: var(--signal);
  }

  .skip {
    position: absolute;
    top: 22px;
    right: 26px;
    display: flex;
    gap: 8px;
    align-items: center;
    font-size: 12px;
    letter-spacing: 0.14em;
    color: var(--ink-3);
  }

  .skip:hover {
    color: var(--ink);
  }

  .armed .ember-glow {
    animation: ember calc(3200ms * var(--k)) var(--ease-out) forwards;
  }

  .armed .ring {
    animation: draw calc(900ms * var(--k)) var(--ease-out) calc(450ms * var(--k)) forwards, show 1ms linear calc(450ms * var(--k)) forwards;
  }

  .armed .satellite {
    animation: show calc(400ms * var(--k)) var(--ease-out) calc(1100ms * var(--k)) forwards;
  }

  .armed .ring-dash {
    animation: show calc(700ms * var(--k)) var(--ease-out) calc(750ms * var(--k)) forwards;
  }

  .armed .flame {
    animation: flame calc(2400ms * var(--k)) var(--ease-out) calc(950ms * var(--k)) forwards;
  }

  .armed .outline {
    animation:
      show 1ms linear calc(650ms * var(--k)) forwards,
      draw calc(1050ms * var(--k)) var(--ease-in-out) calc(650ms * var(--k)) forwards,
      vanish calc(500ms * var(--k)) var(--ease-out) calc(1900ms * var(--k)) forwards;
  }

  .armed .fill {
    animation: show calc(520ms * var(--k)) var(--ease-out) calc(1480ms * var(--k)) forwards;
  }

  .armed .sheen {
    animation: sheen calc(900ms * var(--k)) var(--ease-in-out) calc(1850ms * var(--k)) forwards;
  }

  .armed .spark {
    animation: spark calc(1300ms * var(--k)) var(--ease-out) calc(60ms * var(--k)) forwards;
  }

  .armed .flares rect {
    animation: flare calc(1100ms * var(--k)) var(--ease-out) calc(160ms * var(--k)) forwards;
  }

  .armed .flares .diag {
    animation-delay: calc(260ms * var(--k));
  }

  .armed .star {
    animation:
      star-in calc(900ms * var(--k)) var(--ease-out) calc(320ms * var(--k)) forwards,
      glow 1600ms var(--ease-in-out) calc(1250ms * var(--k)) infinite alternate;
  }

  .armed .embers circle {
    animation: ember-rise var(--life) var(--ease-out) calc((1000ms + var(--delay)) * var(--k)) infinite;
  }

  .armed .word path {
    animation: rise-letter calc(620ms * var(--k)) var(--ease-out) forwards;
    animation-delay: calc((1650ms + var(--i) * 70ms) * var(--k));
  }

  .armed .tagline {
    animation: rise calc(600ms * var(--k)) var(--ease-out) calc(2250ms * var(--k)) forwards;
  }

  .armed .skip {
    animation: show 400ms var(--ease-out) 300ms forwards;
  }

  .revealed .fill,
  .revealed .word path,
  .revealed .tagline {
    animation: none;
    opacity: 1;
    transform: none;
  }

  .revealed .star {
    opacity: 1;
    transform: none;
  }

  .revealed .final-star {
    opacity: 1;
  }

  .revealed .fx .star {
    opacity: 0;
  }

  .revealed .outline,
  .revealed .sheen,
  .revealed .spark,
  .revealed .flares rect {
    animation: none;
    opacity: 0;
  }

  .calm .fx,
  .calm .ember-glow {
    display: none;
  }

  .calm.armed .fill,
  .calm.armed .final-star,
  .calm.armed .word path,
  .calm.armed .tagline {
    animation: show 300ms linear forwards;
    transform: none;
  }

  @keyframes draw {
    to {
      stroke-dashoffset: 0;
    }
  }

  @keyframes show {
    to {
      opacity: 1;
    }
  }

  @keyframes vanish {
    from {
      opacity: 1;
    }
    to {
      opacity: 0;
    }
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  @keyframes spark {
    0% {
      opacity: 0;
      transform: scale(0);
    }
    25% {
      opacity: 1;
      transform: scale(2.6);
    }
    60% {
      opacity: 0.9;
      transform: scale(1.4);
    }
    100% {
      opacity: 0;
      transform: scale(0.8);
    }
  }

  @keyframes flare {
    0% {
      opacity: 0;
      transform: scaleX(0);
    }
    35% {
      opacity: 1;
      transform: scaleX(1);
    }
    100% {
      opacity: 0;
      transform: scaleX(0.4);
    }
  }

  @keyframes star-in {
    0% {
      opacity: 0;
      transform: rotate(-216deg) scale(0.15);
    }
    60% {
      opacity: 1;
      transform: rotate(12deg) scale(1.12);
    }
    100% {
      opacity: 1;
      transform: rotate(0) scale(1);
    }
  }

  @keyframes glow {
    from {
      filter: drop-shadow(0 0 0.6px #ffb54a);
    }
    to {
      filter: drop-shadow(0 0 3px #ff9a4a);
    }
  }

  @keyframes flame {
    0% {
      opacity: 0;
      transform: scale(0.96);
    }
    22% {
      opacity: 0.95;
      transform: scale(1.07);
    }
    34% {
      opacity: 0.7;
    }
    46% {
      opacity: 0.88;
      transform: scale(1.05);
    }
    70% {
      opacity: 0.42;
    }
    100% {
      opacity: 0.16;
      transform: scale(1.035);
    }
  }

  @keyframes sheen {
    0% {
      opacity: 1;
      transform: translateX(0) skewX(-14deg);
    }
    100% {
      opacity: 1;
      transform: translateX(190px) skewX(-14deg);
    }
  }

  @keyframes ember-rise {
    0% {
      opacity: 0;
      transform: translate(0, 0) scale(1);
    }
    15% {
      opacity: 0.9;
    }
    100% {
      opacity: 0;
      transform: translate(var(--drift), -78px) scale(0.3);
    }
  }

  @keyframes rise-letter {
    to {
      transform: translateY(0);
    }
  }

  @keyframes rise {
    from {
      opacity: 0;
      translate: 0 8px;
    }
    to {
      opacity: 1;
      translate: 0 0;
    }
  }

  @keyframes ember {
    0% {
      opacity: 0;
      transform: scale(0.6);
    }
    45% {
      opacity: 1;
      transform: scale(1);
    }
    100% {
      opacity: 0.55;
      transform: scale(1.05);
    }
  }
</style>
