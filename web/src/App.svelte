<script>
  import { onMount, tick, untrack } from 'svelte';
  import { fly, fade } from 'svelte/transition';
  import { cubicOut } from 'svelte/easing';
  import { prefersReducedMotion } from 'svelte/motion';
  import { station, TOP_K } from './lib/station.svelte.js';
  import { api } from './lib/api.js';
  import { readHash, writeHash } from './lib/hash.js';
  import { LEVELS } from './lib/format.js';
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
  import emblem from './assets/brand/yildiz-emblem.png';

  const ARRIVED_KEY = 'istasyon.arrived';

  let width = $state(typeof window === 'undefined' ? 1440 : window.innerWidth);
  let searchInput = $state();
  let arrival = $state(false);
  let quickArrival = $state(false);
  let hashReady = false;
  let controller;
  let timer;

  const motion = $derived(prefersReducedMotion.current ? 0 : 1);
  const compact = $derived(width < 860);
  const leftWidth = $derived(width > 1180 ? 404 : 360);
  const rightWidth = $derived(width > 1180 ? 432 : 380);
  const rightOpen = $derived(Boolean(station.dossierId) || station.mode === 'observe');
  const safe = $derived(
    compact
      ? { left: 0, right: 0, top: 0, bottom: 0 }
      : arrival
        ? { left: Math.min(width * 0.48, 760), right: 0, top: 64, bottom: 0 }
        : {
          left: station.mode === 'trust' ? 0 : leftWidth + 40,
          right: rightOpen && station.mode !== 'trust' ? rightWidth + 40 : 0,
          top: 64,
          bottom: 0
        }
  );
  const announcement = $derived(
    station.result?.candidates?.length
      ? `En yakın aday ${station.result.candidates[0].name}. Güven ${LEVELS[station.result.confidence.level].word}.`
      : ''
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
      applyHash(readHash(location.hash));
    };
    window.addEventListener('hashchange', onHash);
    (async () => {
      const initial = readHash(location.hash);
      await station.load();
      if (!station.data) return;
      applyHash(initial);
      const deepLink = initial.techniques.length || initial.actor || initial.mode;
      quickArrival = seenBefore();
      arrival = !deepLink;
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

  function onkeydown(event) {
    if (arrival) return;
    const typing = ['INPUT', 'TEXTAREA'].includes(event.target?.tagName);
    if (event.key === '/' && !typing) {
      event.preventDefault();
      station.mode = 'observe';
      tick().then(() => searchInput?.focus());
    } else if ((event.key === 'm' || event.key === 'M') && !typing && !event.ctrlKey && !event.metaKey) {
      station.mode = 'observe';
      station.matrixOpen = !station.matrixOpen;
    } else if (event.key === 'Escape') {
      if (station.matrixOpen) station.matrixOpen = false;
      else if (station.comparison) station.comparison = null;
      else if (station.dossierId) station.closeDossier();
    }
  }

  function choose(action) {
    remember();
    arrival = false;
    if (action === 'blind') {
      station.startBlind(0).catch((error) => station.notify(error.message));
    } else if (action === 'explore') {
      station.mode = 'explore';
    } else {
      station.mode = 'observe';
      tick().then(() => searchInput?.focus());
    }
  }
</script>

<svelte:window bind:innerWidth={width} {onkeydown} />

<div class="station" class:compact>
  <div class="space">
    {#if station.data}
      <StarMap {safe} intro={arrival && !quickArrival} dim={station.mode === 'trust'} controls={!arrival && station.mode !== 'trust'} />
    {/if}
  </div>

  {#if !arrival}
    <div class="bar-wrap" in:fly={{ y: -16, duration: 520 * motion, easing: cubicOut }}>
      <TopBar />
    </div>
  {/if}

  {#if station.error}
    <div class="fault" in:fade>
      <span class="eyebrow">Bağlantı kurulamadı</span>
      <h1>İstasyon verisine ulaşılamıyor</h1>
      <p>{station.error}</p>
      <p>API çalışıyor mu? Depo kökünde: <code>python -m ttp_similarity.api</code></p>
    </div>
  {:else if !station.data}
    <div class="boot" aria-busy="true">
      <img class="emblem" src={emblem} alt="" width="56" height="56" />
      <span class="mono">istasyon bağlanıyor</span>
    </div>
  {/if}

  {#if station.data && !arrival}
    {#if station.mode === 'trust'}
      <main class="center" in:fly={{ y: 20, duration: 480 * motion, easing: cubicOut }}>
        <Trust />
      </main>
    {:else}
      {#key station.mode}
        <aside class="left" in:fly={{ x: -28, duration: 520 * motion, easing: cubicOut }} aria-label="Kontrol paneli">
          {#if station.mode === 'observe'}
            <Observe bind:searchInput />
          {:else}
            <Explore />
          {/if}
        </aside>
      {/key}
      {#if station.dossierId}
        <aside class="right" aria-label="Aktör dosyası">
          <Dossier />
        </aside>
      {:else if station.mode === 'observe'}
        <aside class="right" in:fly={{ x: 28, duration: 520 * motion, easing: cubicOut }} aria-label="Sonuç">
          <Verdict />
        </aside>
      {/if}
    {/if}
  {/if}

  {#if station.data && arrival}
    <Arrival data={station.data} quick={quickArrival} onchoose={choose} />
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
  }

  .boot .mono {
    font-size: 12px;
    letter-spacing: 0.18em;
    color: var(--ink-3);
    text-transform: uppercase;
  }

  .emblem {
    width: 56px;
    height: 56px;
    animation: breathe 1.8s var(--ease-in-out) infinite;
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
    display: flex;
    flex-direction: column;
  }

  .compact .space {
    position: relative;
    height: 46vh;
    order: 1;
  }

  .compact .left,
  .compact .right,
  .compact .center {
    position: relative;
    inset: auto;
    width: auto;
    margin: 12px;
    order: 2;
  }

  .compact .right {
    order: 3;
  }
</style>
