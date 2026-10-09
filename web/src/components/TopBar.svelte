<script>
  import { station } from '../lib/station.svelte.js';
  import Emblem from './brand/Emblem.svelte';
  import Wordmark from './brand/Wordmark.svelte';

  const modes = [
    { id: 'observe', label: 'Gözlem', hint: 'Gözlenen teknikleri bilinen aktörlerle karşılaştır' },
    { id: 'explore', label: 'Harita', hint: 'Aktör uzayını ve takımyıldızları gez' },
    { id: 'trust', label: 'Güven', hint: 'İstasyon ne kadar isabetli, ölçülmüş hâli' }
  ];

  const active = $derived(Math.max(0, modes.findIndex((m) => m.id === station.mode)));

  function choose(id) {
    station.mode = id;
    if (id === 'trust') station.loadTrust();
    if (id !== 'explore') station.constellationFocus = null;
  }
</script>

<header class="bar">
  <div class="brand">
    <a class="lockup" href="#" aria-label="YILDIZ CTI — başa dön" onclick={(event) => { event.preventDefault(); station.mode = 'observe'; station.closeDossier(); station.recenter(); }}>
      <Emblem size={28} twinkle />
      <Wordmark height={15} />
    </a>
    <span class="rule" aria-hidden="true"></span>
    <span class="name">TTP benzerlik<br />istasyonu</span>
  </div>

  <nav class="modes" style:--active={active} aria-label="Bölümler">
    <span class="indicator" aria-hidden="true"></span>
    {#each modes as mode}
      <button
        class:on={station.mode === mode.id}
        aria-current={station.mode === mode.id ? 'page' : undefined}
        title={mode.hint}
        onclick={() => choose(mode.id)}
      >
        {mode.label}
      </button>
    {/each}
  </nav>

  <div class="meta mono">
    {#if station.data}
      <span>ATT&CK v{station.data.dataset.attack_version}</span>
      <span class="sep"></span>
      <span>{station.data.dataset.actor_count} aktör</span>
      <span class="sep"></span>
      <span>{station.data.dataset.technique_count} teknik</span>
    {/if}
    <span class="principle" title={station.data?.disclaimer}>benzerlik ≠ faillik</span>
  </div>
</header>

<style>
  .bar {
    position: absolute;
    inset: 0 0 auto 0;
    height: var(--bar);
    display: grid;
    grid-template-columns: 1fr auto 1fr;
    align-items: center;
    padding: 0 var(--gap);
    z-index: 20;
    background: linear-gradient(180deg, rgba(4, 6, 10, 0.92), rgba(4, 6, 10, 0));
  }

  .brand {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .lockup {
    display: flex;
    align-items: center;
    gap: 9px;
    color: var(--ink);
    text-decoration: none;
  }

  .rule {
    width: 1px;
    height: 24px;
    background: var(--seam-3);
  }

  .name {
    font-size: 11.5px;
    line-height: 1.2;
    letter-spacing: 0.04em;
    color: var(--ink-3);
  }

  .modes {
    position: relative;
    display: grid;
    grid-template-columns: repeat(3, 108px);
    border: 1px solid var(--seam-2);
    background: rgba(10, 15, 23, 0.86);
    padding: 3px;
  }

  .indicator {
    position: absolute;
    top: 3px;
    bottom: 3px;
    left: 3px;
    width: 108px;
    background: var(--hull-3);
    border-bottom: 2px solid var(--signal);
    transform: translateX(calc(var(--active) * 100%));
    transition: transform var(--t-base) var(--ease-out);
  }

  .modes button {
    position: relative;
    height: 32px;
    font-size: 13px;
    font-weight: 500;
    color: var(--ink-3);
    letter-spacing: 0.02em;
    transition: color var(--t-fast);
  }

  .modes button:hover,
  .modes button.on {
    color: var(--ink);
  }

  .meta {
    justify-self: end;
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 12px;
    color: var(--ink-3);
  }

  .sep {
    width: 3px;
    height: 3px;
    background: var(--seam-3);
  }

  .principle {
    margin-left: 10px;
    padding: 4px 9px;
    border: 1px solid var(--signal-line);
    color: var(--signal);
    letter-spacing: 0.04em;
  }

  @media (max-width: 1180px) {
    .meta > span:not(.principle),
    .meta .sep {
      display: none;
    }
  }

  @media (max-width: 860px) {
    .bar {
      position: sticky;
      top: 0;
      grid-template-columns: auto 1fr;
      gap: 12px;
      background: var(--void);
      border-bottom: 1px solid var(--seam);
    }
    .meta {
      display: none;
    }
    .modes {
      grid-template-columns: repeat(3, 1fr);
      justify-self: end;
      width: min(100%, 300px);
    }
    .indicator {
      width: calc((100% - 6px) / 3);
    }
  }
</style>
