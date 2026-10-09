<script>
  import { station } from '../lib/station.svelte.js';
  import Emblem from './brand/Emblem.svelte';
  import Wordmark from './brand/Wordmark.svelte';

  let { compact = false, visible = true } = $props();

  const modes = [
    { id: 'observe', label: 'Gözlem', hint: 'Gözlenen teknikleri bilinen aktörlerle karşılaştır', icon: 'M4 12h4l2-6 4 12 2-6h4' },
    { id: 'explore', label: 'Harita', hint: 'Aktör uzayını ve takımyıldızları gez', icon: 'M5 18l4-9 5 5 5-9' },
    { id: 'trust', label: 'Güven', hint: 'İstasyon ne kadar isabetli, ölçülmüş hâli', icon: 'M12 3l7 3v5c0 4.5-3 8.2-7 10-4-1.8-7-5.5-7-10V6l7-3zM9 12l2 2 4-4' }
  ];

  const active = $derived(Math.max(0, modes.findIndex((m) => m.id === station.mode)));

  function choose(id) {
    station.mode = id;
    if (id === 'trust') station.loadTrust();
    if (id !== 'explore') station.constellationFocus = null;
    if (compact) window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function home(event) {
    event.preventDefault();
    station.mode = 'observe';
    station.focus = false;
    station.closeDossier();
    station.recenter();
  }
</script>

<header class="bar" class:compact class:hidden={!visible} aria-hidden={visible ? undefined : 'true'}>
  <div class="brand">
    <a class="lockup" href="#" aria-label="YILDIZ CTI — başa dön" onclick={home} data-brand-slot="bar" tabindex={visible ? undefined : -1}>
      <span class="part" data-brand="emblem"><Emblem size={compact ? 28 : 32} twinkle /></span>
      <span class="part" data-brand="word"><Wordmark height={compact ? 15 : 17} /></span>
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
        <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
          <path d={mode.icon} fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
        <span>{mode.label}</span>
      </button>
    {/each}
  </nav>

  <div class="meta mono">
    {#if station.data}
      <span class="facts">ATT&CK v{station.data.dataset.attack_version}</span>
      <span class="sep facts"></span>
      <span class="facts">{station.data.dataset.actor_count} aktör</span>
      <span class="sep facts"></span>
      <span class="facts">{station.data.dataset.technique_count} teknik</span>
    {/if}
    {#if !compact && station.mode !== 'trust'}
      <button
        class="focus"
        class:on={station.focus}
        aria-pressed={station.focus}
        title="Odak modu: paneller gizlenir, harita tam ekran (F)"
        onclick={() => (station.focus = !station.focus)}
      >
        <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
          {#if station.focus}
            <path d="M9 4v5H4M15 4v5h5M9 20v-5H4M15 20v-5h5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
          {:else}
            <path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
          {/if}
        </svg>
        <span class="kbd">F</span>
      </button>
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
    gap: 16px;
    padding: 0 var(--gap);
    z-index: 20;
    background: linear-gradient(180deg, rgba(4, 6, 10, 0.92), rgba(4, 6, 10, 0));
  }

  .brand {
    display: flex;
    align-items: center;
    gap: 12px;
    min-width: 0;
  }

  .lockup {
    display: flex;
    align-items: center;
    gap: 10px;
    color: var(--ink);
    text-decoration: none;
  }

  .part {
    display: block;
  }

  .bar {
    transition: opacity var(--t-slow) var(--ease-out);
  }

  .bar.hidden {
    opacity: 0;
    pointer-events: none;
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
    white-space: nowrap;
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
    width: calc((100% - 6px) / 3);
    background: var(--hull-3);
    border-bottom: 2px solid var(--signal);
    transform: translateX(calc(var(--active) * 100%));
    transition: transform var(--t-base) var(--ease-out);
  }

  .modes button {
    position: relative;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 7px;
    font-size: 13px;
    font-weight: 500;
    color: var(--ink-3);
    letter-spacing: 0.02em;
    transition: color var(--t-fast);
  }

  .modes button svg {
    display: none;
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

  .focus {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    height: 32px;
    padding: 0 8px;
    margin-left: 6px;
    border: 1px solid var(--seam-2);
    color: var(--ink-2);
    background: rgba(10, 15, 23, 0.86);
  }

  .focus:hover,
  .focus.on {
    color: var(--signal);
    border-color: var(--signal-line);
  }

  .principle {
    padding: 4px 9px;
    border: 1px solid var(--signal-line);
    color: var(--signal);
    letter-spacing: 0.04em;
    white-space: nowrap;
  }

  @media (max-width: 1480px) {
    .facts {
      display: none;
    }
  }

  .compact {
    position: relative;
    grid-template-columns: auto 1fr auto;
    background: rgba(4, 6, 10, 0.97);
    border-bottom: 1px solid var(--seam);
  }

  @media (max-width: 639px) {
    .compact {
      grid-template-columns: auto 1fr;
    }

    .name,
    .rule {
      display: none;
    }

    .principle {
      font-size: 11px;
      padding: 3px 7px;
    }

    .modes {
      position: fixed;
      left: 0;
      right: 0;
      bottom: 0;
      z-index: 40;
      grid-template-columns: repeat(3, 1fr);
      padding: 6px 8px calc(6px + env(safe-area-inset-bottom));
      border: 0;
      border-top: 1px solid var(--seam-2);
      background: rgba(10, 15, 23, 0.98);
    }

    .indicator {
      top: 6px;
      bottom: calc(6px + env(safe-area-inset-bottom));
      left: 8px;
      width: calc((100% - 16px) / 3);
      border-bottom: 0;
      border-top: 2px solid var(--signal);
    }

    .modes button {
      height: 52px;
      flex-direction: column;
      gap: 3px;
      font-size: 11.5px;
    }

    .modes button svg {
      display: block;
    }
  }
</style>
