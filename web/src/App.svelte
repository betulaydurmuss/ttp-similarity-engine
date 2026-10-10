<script>
  import { onMount, tick, untrack } from 'svelte';
  import { fly, fade } from 'svelte/transition';
  import { cubicOut } from 'svelte/easing';
  import { prefersReducedMotion } from 'svelte/motion';
  import { station, TOP_K } from './lib/station.svelte.js';
  import { api } from './lib/api.js';
  import { readHash, writeHash } from './lib/hash.js';
  import { LEVELS } from './lib/format.js';
  import { layoutTier, panelWidths } from './lib/layout.js';
  import { flyBrand } from './lib/flight.js';
  import StarMap from './components/StarMap.svelte';
  import TopBar from './components/TopBar.svelte';
  import Arrival from './components/Arrival.svelte';
  import Observe from './components/Observe.svelte';
  import Verdict from './components/Verdict.svelte';
  import Dossier from './components/Dossier.svelte';
  import Explore from './components/Explore.svelte';
  import Trust from './components/Trust.svelte';
  import MatrixPicker from './components/MatrixPicker.svelte';
  import Compare from './components/Compare.svelte';
  import Toast from './components/Toast.svelte';
  import Emblem from './components/brand/Emblem.svelte';
  import Ignition from './components/brand/Ignition.svelte';

  const ARRIVED_KEY = 'istasyon.arrived';
  const IGNITED_KEY = 'yildiz.ignited';

  let width = $state(typeof window === 'undefined' ? 1440 : window.innerWidth);
  let height = $state(typeof window === 'undefined' ? 900 : window.innerHeight);
  let searchInput = $state();
  let rightPanel = $state();
  const initial = readHash(typeof location === 'undefined' ? '' : location.hash);
  const deepLink = Boolean(initial.techniques.length || initial.actor || initial.mode);
  let arrival = $state(!deepLink);
  let ignition = $state(true);
  const variant = initialVariant();
  let quickArrival = $state(false);
  let burst = $state(true);
  let verdictVisible = $state(true);
  let hashReady = false;
  let controller;
  let timer;

  const motion = $derived(prefersReducedMotion.current ? 0 : 1);
  const tier = $derived(layoutTier(width));
  const compact = $derived(tier === 'phone' || tier === 'tablet');
  const widths = $derived(panelWidths(tier, width));
  const bar = $derived(height <= 820 ? 56 : 64);
  const gap = $derived(height <= 820 ? 14 : 20);
  const rightOpen = $derived(Boolean(station.dossierId) || station.mode === 'observe');
  const panelsShown = $derived(!station.focus || compact);
  const safe = $derived(
    compact
      ? { left: 0, right: 0, top: 0, bottom: 0 }
      : arrival
        ? { left: Math.min(width * 0.48, 760), right: 0, top: bar, bottom: 0 }
        : {
            left: station.mode === 'trust' || !panelsShown ? 0 : widths.left + gap * 2,
            right: rightOpen && station.mode !== 'trust' && panelsShown ? widths.right + gap * 2 : 0,
            top: bar,
            bottom: 0
          }
  );
  const top = $derived(station.result?.candidates?.[0] ?? null);
  const showPill = $derived(compact && !arrival && station.mode === 'observe' && top && !verdictVisible && !station.dossierId);
  const announcement = $derived(
    top ? `En yakın aday ${top.name}. Güven ${LEVELS[station.result.confidence.level].word}.` : ''
  );

  function remember() {
    try {
      localStorage.setItem(ARRIVED_KEY, '1');
    } catch {}
  }

  function seenBefore() {
    try {
      return localStorage.getItem(ARRIVED_KEY) === '1';
    } catch {
      return false;
    }
  }

  function initialVariant() {
    if (typeof window === 'undefined') return 'full';
    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return 'calm';
    return deepLink || ignitedThisSession() ? 'short' : 'full';
  }

  function ignitedThisSession() {
    try {
      return sessionStorage.getItem(IGNITED_KEY) === '1';
    } catch {
      return true;
    }
  }

  function ignited() {
    try {
      sessionStorage.setItem(IGNITED_KEY, '1');
    } catch {}
    ignition = false;
    setTimeout(() => (burst = false), 2600);
  }

  function landingSlot() {
    if (station.error) return null;
    return document.querySelector(arrival ? '[data-brand-slot="arrival"]' : '[data-brand-slot="bar"]');
  }

  function applyHash(state) {
    station.mode = state.mode ?? 'observe';
    if (station.mode === 'trust') station.loadTrust();
    station.selected = [];
    station.noise = [];
    station.blind = null;
    station.add(state.techniques);
    station.noise = state.noise.filter((id) => station.vocabulary.has(id) && !station.selected.includes(id));
    if (state.actor) station.openDossier(state.actor);
    else station.closeDossier();
  }

  onMount(() => {
    const onHash = () => {
      if (!station.data) return;
      arrival = false;
      ignition = false;
      applyHash(readHash(location.hash));
    };
    window.addEventListener('hashchange', onHash);
    quickArrival = seenBefore();
    (async () => {
      await station.load();
      if (!station.data) return;
      applyHash(initial);
      hashReady = true;
    })();
    return () => window.removeEventListener('hashchange', onHash);
  });

  $effect(() => {
    const query = station.query;
    untrack(() => {
      clearTimeout(timer);
      if (!station.data) return;
      if (!query.length) {
        controller?.abort();
        station.result = null;
        station.previousRanks = {};
        station.busy = false;
        return;
      }
      timer = setTimeout(async () => {
        controller?.abort();
        const own = new AbortController();
        controller = own;
        const slow = setTimeout(() => (station.busy = true), 200);
        try {
          station.setResult(await api.query(query, TOP_K, own.signal));
        } catch (error) {
          if (error.name !== 'AbortError') station.notify(error.message);
        } finally {
          clearTimeout(slow);
          if (controller === own) station.busy = false;
        }
      }, 140);
    });
  });

  $effect(() => {
    const hash = writeHash({
      techniques: station.selected,
      noise: station.noise,
      actor: station.dossierId,
      mode: station.mode
    });
    if (hashReady && hash !== location.hash) {
      history.replaceState(null, '', hash || location.pathname + location.search);
    }
  });

  $effect(() => {
    const panel = rightPanel;
    if (!panel || !compact) {
      verdictVisible = true;
      return;
    }
    const observer = new IntersectionObserver(([entry]) => (verdictVisible = entry.isIntersecting), {
      rootMargin: '0px 0px -30% 0px'
    });
    observer.observe(panel);
    return () => observer.disconnect();
  });

  $effect(() => {
    const id = station.dossierId;
    untrack(() => {
      if (id && compact) {
        setTimeout(scrollToResult, 60);
        setTimeout(scrollToResult, 360);
      }
    });
  });

  function scrollToResult() {
    const label = station.dossierId ? 'Aktör dosyası' : 'Sonuç';
    const panel = document.querySelector(`aside.right[aria-label="${label}"]`) ?? rightPanel;
    if (!panel) return;
    const offset = document.querySelector('.bar-wrap')?.getBoundingClientRect().height ?? 0;
    const top = panel.getBoundingClientRect().top + window.scrollY - offset - 8;
    window.scrollTo({ top, behavior: motion ? 'smooth' : 'auto' });
  }

  function onkeydown(event) {
    if (arrival || ignition) return;
    const typing = ['INPUT', 'TEXTAREA'].includes(event.target?.tagName);
    if (typing || event.ctrlKey || event.metaKey || event.altKey) {
      if (event.key === 'Escape' && typing) event.target.blur();
      return;
    }
    if (event.key === '/') {
      event.preventDefault();
      station.mode = 'observe';
      station.focus = false;
      tick().then(() => searchInput?.focus());
    } else if (event.key === 'm' || event.key === 'M') {
      station.mode = 'observe';
      station.matrixOpen = !station.matrixOpen;
    } else if ((event.key === 'f' || event.key === 'F') && !compact) {
      station.focus = !station.focus;
    } else if (event.key === 'Escape') {
      if (station.matrixOpen) station.matrixOpen = false;
      else if (station.comparison) station.comparison = null;
      else if (station.dossierId) station.closeDossier();
      else if (station.focus) station.focus = false;
    }
  }

  function choose(action) {
    remember();
    flyBrand(
      document.querySelector('[data-brand-slot="arrival"]'),
      document.querySelector('[data-brand-slot="bar"]'),
      { duration: motion ? 820 : 0 }
    );
    arrival = false;
    if (action === 'blind') {
      station.startBlind(0).catch((error) => station.notify(error.message));
    } else if (action === 'explore') {
      station.mode = 'explore';
    } else {
      station.mode = 'observe';
      if (!compact) tick().then(() => searchInput?.focus());
    }
  }
</script>

<svelte:window bind:innerWidth={width} bind:innerHeight={height} {onkeydown} />

<div
  class="station tier-{tier}"
  class:compact
  class:focus={station.focus && !compact}
  style:--panel-left="{widths.left}px"
  style:--panel-right="{widths.right}px"
  style:--bar="{bar}px"
  style:--gap="{gap}px"
>
  <div class="space">
    {#if station.data}
      <StarMap
        {safe}
        intro={burst}
        hold={ignition}
        dim={station.mode === 'trust'}
        controls={!arrival && station.mode !== 'trust'}
      />
    {/if}
  </div>

  {#if station.data}
    <div class="bar-wrap">
      <TopBar {compact} visible={!arrival} />
    </div>
  {/if}

  {#if station.error}
    <div class="fault" in:fade>
      <span class="eyebrow">Bağlantı kurulamadı</span>
      <h1>İstasyon verisine ulaşılamıyor</h1>
      <p>{station.error}</p>
      <p>API çalışıyor mu? Depo kökünde: <code>python -m ttp_similarity.api</code></p>
    </div>
  {:else if !station.data && !ignition}
    <div class="boot" aria-busy="true">
      <div class="orbit">
        <Emblem size={52} />
      </div>
      <span class="mono">istasyon bağlanıyor</span>
    </div>
  {/if}

  {#if station.data && !arrival}
    {#if station.mode === 'trust'}
      <main class="center" in:fly={{ y: 20, duration: 480 * motion, easing: cubicOut }}>
        <Trust />
      </main>
    {:else if panelsShown}
      {#key station.mode}
        <aside
          class="left"
          class:solo={!rightOpen}
          in:fly={{ x: -28, duration: 520 * motion, easing: cubicOut }}
          out:fly={{ x: -28, duration: compact ? 0 : 260 * motion }}
          aria-label="Kontrol paneli"
        >
          {#if station.mode === 'observe'}
            <Observe bind:searchInput />
          {:else}
            <Explore />
          {/if}
        </aside>
      {/key}
      {#if station.dossierId}
        <aside class="right" bind:this={rightPanel} aria-label="Aktör dosyası" out:fly={{ x: 28, duration: compact ? 0 : 260 * motion }}>
          <Dossier />
        </aside>
      {:else if station.mode === 'observe'}
        <aside
          class="right"
          bind:this={rightPanel}
          in:fly={{ x: 28, duration: 520 * motion, easing: cubicOut }}
          out:fly={{ x: 28, duration: compact ? 0 : 260 * motion }}
          aria-label="Sonuç"
        >
          <Verdict />
        </aside>
      {/if}
    {/if}
  {/if}

  {#if showPill}
    <button class="pill level-{station.result.confidence.level}" onclick={scrollToResult} transition:fly={{ y: 24, duration: 320 * motion }}>
      <span class="mono rank">01</span>
      <span class="who">{top.name}</span>
      <span class="mono lvl">{LEVELS[station.result.confidence.level].label}</span>
      <span class="go" aria-hidden="true">↓</span>
      <span class="sr-only">sonuca git</span>
    </button>
  {/if}

  {#if station.data && arrival}
    <Arrival data={station.data} quick={quickArrival} start={!ignition} onchoose={choose} />
  {/if}

  {#if ignition}
    <Ignition
      {variant}
      ready={Boolean(station.data || station.error)}
      landing={landingSlot}
      onlanded={ignited}
    />
  {/if}

  {#if station.matrixOpen}
    <MatrixPicker />
  {/if}
  {#if station.comparison}
    <Compare />
  {/if}
  <Toast />
  <div class="sr-only" aria-live="polite">{announcement}</div>
</div>

<style>
  .station {
    position: relative;
    height: 100%;
    overflow: hidden;
  }

  .space {
    position: absolute;
    inset: 0;
  }

  .bar-wrap {
    position: relative;
    z-index: 20;
  }

  .left,
  .right,
  .center {
    position: absolute;
    top: calc(var(--bar) + 4px);
    bottom: var(--gap);
    z-index: 10;
    display: flex;
    flex-direction: column;
    min-height: 0;
  }

  .left {
    left: var(--gap);
    width: var(--panel-left);
  }

  .right {
    right: var(--gap);
    width: var(--panel-right);
  }

  .left > :global(.panel),
  .right > :global(.panel) {
    flex: 1;
  }

  .center {
    left: var(--gap);
    right: var(--gap);
    margin: 0 auto;
    max-width: 1180px;
  }

  .boot,
  .fault {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 14px;
    z-index: 5;
    text-align: center;
    padding: 24px;
  }

  .boot .mono {
    font-size: 12px;
    letter-spacing: 0.18em;
    color: var(--ink-3);
    text-transform: uppercase;
  }

  .orbit {
    position: relative;
    display: grid;
    place-items: center;
    width: 96px;
    height: 96px;
    color: var(--ink);
    animation: breathe 1.8s var(--ease-in-out) infinite;
  }

  .orbit::before {
    content: '';
    position: absolute;
    inset: 0;
    border-radius: 50%;
    border: 1px solid var(--seam-2);
    border-top-color: var(--signal);
    animation: spin 1.4s linear infinite;
  }

  .fault h1 {
    margin: 0;
    font-weight: 300;
    font-size: 28px;
  }

  .fault p {
    margin: 0;
    color: var(--ink-2);
  }

  .fault code {
    font-family: var(--mono);
    color: var(--signal);
  }

  .pill {
    position: fixed;
    z-index: 30;
    left: 50%;
    bottom: calc(76px + env(safe-area-inset-bottom));
    transform: translateX(-50%);
    display: flex;
    align-items: center;
    gap: 10px;
    max-width: calc(100vw - 32px);
    height: 44px;
    padding: 0 16px;
    background: var(--hull-3);
    border: 1px solid var(--signal-line);
    box-shadow: 0 16px 40px -10px rgba(0, 0, 0, 0.9);
    --level: var(--danger);
  }

  .pill.level-high {
    --level: var(--lock);
  }

  .pill.level-medium {
    --level: var(--signal);
  }

  .pill .rank {
    color: var(--signal);
    font-size: 12px;
  }

  .pill .who {
    font-weight: 500;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .pill .lvl {
    font-size: 11px;
    letter-spacing: 0.1em;
    color: var(--level);
  }

  .pill .go {
    color: var(--ink-3);
  }

  .tier-tablet .pill {
    bottom: 20px;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  @keyframes breathe {
    50% {
      opacity: 0.35;
      transform: scale(0.94);
    }
  }

  .compact {
    height: auto;
    min-height: 100%;
    overflow: visible;
    display: grid;
    grid-template-columns: minmax(0, 1fr);
    grid-template-areas: 'bar' 'map' 'left' 'right';
    align-content: start;
  }

  .compact .bar-wrap {
    grid-area: bar;
    position: sticky;
    top: 0;
  }

  .compact .space {
    grid-area: map;
    position: relative;
    height: clamp(300px, 46vh, 520px);
  }

  .compact .left,
  .compact .right,
  .compact .center {
    position: relative;
    inset: auto;
    width: auto;
    margin: 12px;
  }

  .compact .left {
    grid-area: left;
  }

  .compact .right {
    grid-area: right;
  }

  .compact .center {
    grid-column: 1 / -1;
  }

  .compact.tier-tablet {
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
    grid-template-areas: 'bar bar' 'map map' 'left right';
  }

  .compact.tier-tablet .left {
    margin-right: 6px;
  }

  .compact.tier-tablet .right {
    margin-left: 6px;
  }

  .compact.tier-tablet .left.solo {
    grid-column: 1 / -1;
    margin-right: 12px;
  }

  .compact.tier-phone {
    padding-bottom: calc(72px + env(safe-area-inset-bottom));
  }
</style>
