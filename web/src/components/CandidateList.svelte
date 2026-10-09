<script>
  import { flip } from 'svelte/animate';
  import { fly } from 'svelte/transition';
  import { cubicOut } from 'svelte/easing';
  import { prefersReducedMotion } from 'svelte/motion';
  import { station } from '../lib/station.svelte.js';
  import { dec, pct } from '../lib/format.js';

  let { result } = $props();

  const motion = $derived(prefersReducedMotion.current ? 0 : 1);
  const top = $derived(result.candidates[0]?.score || 1);
  const known = $derived(result.query.known.length);
  const hadPrevious = $derived(Object.keys(station.previousRanks).length > 0);
  const gap = $derived(
    result.candidates.length > 1 ? (result.candidates[0].score - result.candidates[1].score) / result.candidates[0].score : null
  );
  const answer = $derived(station.blind?.revealed ? station.blind.answer.id : null);

  function delta(candidate) {
    if (!hadPrevious) return null;
    const before = station.previousRanks[candidate.id];
    if (before === undefined) return { text: 'yeni', kind: 'new' };
    if (before > candidate.rank) return { text: `▲${before - candidate.rank}`, kind: 'up' };
    if (before < candidate.rank) return { text: `▼${candidate.rank - before}`, kind: 'down' };
    return null;
  }
</script>

<ol class="list" aria-label="Aday aktörler">
  {#each result.candidates as candidate (candidate.id)}
    {@const change = delta(candidate)}
    <li
      animate:flip={{ duration: 520 * motion, easing: cubicOut }}
      in:fly={{ x: 16, duration: 360 * motion, delay: candidate.rank * 30 * motion }}
      class:first={candidate.rank === 1}
      class:answer={answer === candidate.id}
      class:hover={station.hover === candidate.id}
    >
      <button
        onclick={() => station.openDossier(candidate.id)}
        onpointerenter={() => (station.hover = candidate.id)}
        onpointerleave={() => station.hover === candidate.id && (station.hover = null)}
        onfocus={() => (station.hover = candidate.id)}
      >
        <span class="rank mono">{String(candidate.rank).padStart(2, '0')}</span>
        <span class="who">
          <span class="name">{candidate.name}</span>
          <span class="sub mono">
            {candidate.id}
            {#if candidate.aliases.length}· {candidate.aliases[0]}{/if}
          </span>
        </span>
        <span class="bar" aria-hidden="true"><i style:width="{(candidate.score / top) * 100}%"></i></span>
        <span class="score mono">{dec(candidate.score, 3)}</span>
        <span class="match mono" title="Eşleşen / skorlanan teknik">{candidate.matched.length}/{known}</span>
        {#if change}
          {#key `${candidate.id}${candidate.rank}${result.query.known.length}`}
            <span class="delta {change.kind} mono">{change.text}</span>
          {/key}
        {/if}
        {#if answer === candidate.id}<span class="tag mono">gizli aktör</span>{/if}
      </button>
      {#if candidate.rank === 1 && gap !== null}
        <div class="gap" aria-label="Birinci ve ikinci aday arasındaki ayrışma">
          <span class="gap-line" style:--gap={Math.min(1, gap / 0.3)}></span>
          <span class="mono">ayrışma {pct(gap)}</span>
        </div>
      {/if}
    </li>
  {/each}
</ol>

<style>
  .list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 2px;
  }

  li button {
    position: relative;
    width: 100%;
    display: grid;
    grid-template-columns: 26px minmax(0, 1fr) 72px 50px 36px;
    gap: 10px;
    align-items: center;
    padding: 9px 10px;
    text-align: left;
    border: 1px solid transparent;
    transition: background var(--t-fast), border-color var(--t-fast);
  }

  li button:hover,
  li.hover button {
    background: var(--hull-3);
    border-color: var(--seam-2);
  }

  li.first button {
    background: var(--signal-soft);
    border-color: var(--signal-line);
  }

  li.answer button {
    border-color: var(--lock);
    box-shadow: inset 3px 0 0 var(--lock);
  }

  .rank {
    font-size: 13px;
    color: var(--ink-3);
  }

  li.first .rank {
    color: var(--signal);
  }

  .who {
    min-width: 0;
    display: flex;
    flex-direction: column;
  }

  .name {
    font-size: 14px;
    font-weight: 500;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .sub {
    font-size: 11.5px;
    color: var(--ink-3);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .bar {
    height: 4px;
    background: var(--seam);
  }

  .bar i {
    display: block;
    height: 100%;
    background: var(--ink-3);
    transition: width var(--t-slow) var(--ease-out);
  }

  li.first .bar i {
    background: var(--signal);
  }

  .score {
    font-size: 13px;
    text-align: right;
  }

  .match {
    font-size: 12px;
    color: var(--ink-3);
    text-align: right;
  }

  .delta {
    position: absolute;
    right: -6px;
    top: -7px;
    font-size: 10.5px;
    padding: 0 4px;
    background: var(--hull);
    border: 1px solid var(--seam-2);
    animation: blink 2600ms var(--ease-out) forwards;
  }

  .delta.up {
    color: var(--lock);
  }

  .delta.down {
    color: var(--danger);
  }

  .delta.new {
    color: var(--signal);
  }

  .tag {
    position: absolute;
    right: 8px;
    bottom: -8px;
    font-size: 10.5px;
    padding: 0 5px;
    color: var(--void);
    background: var(--lock);
  }

  .gap {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 4px 10px 8px 46px;
    font-size: 11.5px;
    color: var(--ink-3);
  }

  .gap-line {
    position: relative;
    flex: 1;
    height: 1px;
    background: var(--seam-2);
  }

  .gap-line::after {
    content: '';
    position: absolute;
    left: 0;
    top: -2px;
    height: 5px;
    width: calc(var(--gap) * 100%);
    background: var(--signal-line);
    transition: width var(--t-slow) var(--ease-out);
  }

  @keyframes blink {
    0% {
      opacity: 0;
      translate: 0 4px;
    }
    12%,
    70% {
      opacity: 1;
      translate: 0 0;
    }
    100% {
      opacity: 0;
    }
  }
</style>
