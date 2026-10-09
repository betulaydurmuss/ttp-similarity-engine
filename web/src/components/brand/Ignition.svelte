<script>
  import { onMount } from 'svelte';
  import { prefersReducedMotion } from 'svelte/motion';
  import { EMBLEM_BODY, EMBLEM_STAR, STAR_CENTER, WORD_LETTERS, WORD_WIDTH } from '../../lib/brand.js';

  let { ondone } = $props();

  const calm = prefersReducedMotion.current;
  const HOLD = calm ? 900 : 3150;
  const EXIT = calm ? 250 : 560;

  let leaving = $state(false);
  let finished = false;
  let timers = [];

  const [sx, sy] = STAR_CENTER;

  function finish() {
    if (finished) return;
    finished = true;
    leaving = true;
    timers.push(setTimeout(() => ondone?.(), EXIT));
  }

  onMount(() => {
    timers.push(setTimeout(finish, HOLD));
    const onKey = (event) => {
      if (['Escape', 'Enter', ' '].includes(event.key)) {
        event.preventDefault();
        finish();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => {
      timers.forEach(clearTimeout);
      window.removeEventListener('keydown', onKey);
    };
  });
</script>

<div class="ignition" class:calm class:leaving role="presentation" onclick={finish}>
  <div class="ember" aria-hidden="true"></div>

  <div class="lockup" role="img" aria-label="YILDIZ CTI">
    <svg class="mark" viewBox="-30 -30 160 160" aria-hidden="true">
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
      <path class="fill" d={EMBLEM_BODY} fill-rule="evenodd" />
      <g clip-path="url(#ig-body)">
        <rect class="sheen" x="-60" y="-10" width="46" height="130" fill="url(#ig-sheen)" />
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

    <svg class="word" viewBox="0 0 {WORD_WIDTH} 100" aria-hidden="true">
      {#each WORD_LETTERS as letter, i}
        <path d={letter.d} fill-rule="evenodd" style:--i={i} />
      {/each}
    </svg>

    <p class="tagline mono">CTI · TTP BENZERLİK İSTASYONU</p>
  </div>

  <button class="skip mono" onclick={finish}>ATLA <span class="kbd">Esc</span></button>
</div>

<style>
  .ignition {
    position: fixed;
    inset: 0;
    z-index: 80;
    display: grid;
    place-items: center;
    background:
      radial-gradient(circle at 50% 46%, rgba(255, 140, 60, 0.07), transparent 42%),
      var(--void);
    cursor: pointer;
    transition: background var(--t-slow) var(--ease-out);
  }

  .ignition.leaving {
    background: transparent;
    pointer-events: none;
  }

  .ember {
    position: absolute;
    width: min(70vmin, 620px);
    aspect-ratio: 1;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(255, 123, 58, 0.16), rgba(255, 123, 58, 0) 62%);
    animation: ember 3200ms var(--ease-out) both;
    pointer-events: none;
  }

  .lockup {
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: clamp(10px, 2.4vh, 22px);
    transition:
      opacity var(--t-slow) var(--ease-out),
      transform var(--t-slow) var(--ease-out),
      filter var(--t-slow) var(--ease-out);
  }

  .leaving .lockup {
    opacity: 0;
    transform: scale(1.08);
    filter: blur(6px);
  }

  .mark {
    width: clamp(170px, 34vh, 300px);
    height: auto;
    overflow: visible;
  }

  .ring {
    fill: none;
    stroke: var(--seam-3);
    stroke-width: 0.45;
    stroke-dasharray: 1;
    stroke-dashoffset: 1;
    animation: draw 900ms var(--ease-out) 450ms forwards;
  }

  .satellite {
    fill: var(--ink);
    opacity: 0;
    animation: appear 400ms var(--ease-out) 1100ms forwards;
  }

  .ring-dash {
    fill: none;
    stroke: var(--seam-2);
    stroke-width: 0.35;
    stroke-dasharray: 0.6 3.2;
    opacity: 0;
    animation: appear 700ms var(--ease-out) 750ms forwards;
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
    opacity: 0;
    transform-origin: 50px 52px;
    animation: flame 2400ms var(--ease-out) 950ms forwards;
  }

  .outline {
    fill: none;
    stroke: var(--ink);
    stroke-width: 0.5;
    stroke-linejoin: round;
    stroke-dasharray: 1;
    stroke-dashoffset: 1;
    animation:
      draw 1050ms var(--ease-in-out) 650ms forwards,
      vanish 500ms var(--ease-out) 1900ms forwards;
  }

  .fill {
    fill: var(--ink);
    opacity: 0;
    animation: appear 520ms var(--ease-out) 1480ms forwards;
  }

  .sheen {
    transform: translateX(0) skewX(-14deg);
    animation: sheen 900ms var(--ease-in-out) 1850ms forwards;
    opacity: 0;
  }

  .star-group {
    transform-box: view-box;
    transition:
      transform var(--t-slow) var(--ease-out),
      opacity var(--t-slow) var(--ease-out);
  }

  .leaving .star-group {
    transform: scale(2.4);
    opacity: 0;
  }

  .spark {
    transform-box: fill-box;
    transform-origin: center;
    opacity: 0;
    animation: spark 1300ms var(--ease-out) 60ms forwards;
  }

  .flares rect {
    transform-box: fill-box;
    transform-origin: center;
    opacity: 0;
    animation: flare 1100ms var(--ease-out) 160ms forwards;
  }

  .flares .diag {
    animation-delay: 260ms;
  }

  .star {
    fill: var(--signal);
    transform-box: fill-box;
    transform-origin: center;
    opacity: 0;
    animation:
      star-in 900ms var(--ease-out) 320ms forwards,
      glow 1600ms var(--ease-in-out) 1250ms infinite alternate;
  }

  .word {
    width: clamp(150px, 26vh, 250px);
    height: auto;
    overflow: hidden;
    fill: var(--ink);
  }

  .word path {
    transform-box: fill-box;
    transform: translateY(120%);
    animation: rise-letter 620ms var(--ease-out) forwards;
    animation-delay: calc(1650ms + var(--i) * 70ms);
  }

  .tagline {
    margin: 0;
    font-size: clamp(10.5px, 1.6vh, 12.5px);
    letter-spacing: 0.32em;
    color: var(--ink-3);
    opacity: 0;
    animation: rise 600ms var(--ease-out) 2250ms forwards;
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
    opacity: 0;
    animation: appear 400ms var(--ease-out) 500ms forwards;
  }

  .skip:hover {
    color: var(--ink);
  }

  .calm .ring,
  .calm .outline,
  .calm .flame,
  .calm .sheen,
  .calm .spark,
  .calm .flares rect,
  .calm .satellite,
  .calm .ring-dash,
  .calm .ember {
    display: none;
  }

  .calm .fill,
  .calm .star,
  .calm .word path,
  .calm .tagline,
  .calm .skip {
    animation: appear 300ms linear forwards;
    transform: none;
  }

  @keyframes draw {
    to {
      stroke-dashoffset: 0;
    }
  }

  @keyframes appear {
    to {
      opacity: 1;
    }
  }

  @keyframes vanish {
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
