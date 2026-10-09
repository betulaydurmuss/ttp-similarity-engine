<script>
  import { fade } from 'svelte/transition';
  import { station } from '../lib/station.svelte.js';
  import Panel from './Panel.svelte';
  import TechniqueSearch from './TechniqueSearch.svelte';
  import SignalTray from './SignalTray.svelte';
  import SufficiencyGauge from './SufficiencyGauge.svelte';

  let { searchInput = $bindable() } = $props();
  let working = $state(false);

  async function run(task) {
    if (working) return;
    working = true;
    try {
      await task();
    } catch (error) {
      station.notify(error.message);
    } finally {
      working = false;
    }
  }
</script>

<Panel
  index="01"
  kicker={station.blind ? 'Kör test' : 'Gözlem'}
  title={station.blind ? 'Gizli bir aktörün izleri' : 'Ne gözlemledin?'}
  subtitle={station.blind
    ? `Bilinen bir aktörün tekniklerinin %40'ı${station.blind.noisy ? ', üstüne yaygın gürültü' : ''}. İstasyon onu bulabilecek mi?`
    : 'Olayda gördüğün teknikleri ekle. Nadir olanlar kararı taşır.'}
>
  {#snippet actions()}
    {#if station.query.length}
      <button class="mini" onclick={() => station.clear()} transition:fade={{ duration: 160 }}>Temizle</button>
    {/if}
  {/snippet}

  <TechniqueSearch bind:input={searchInput} />

  {#if station.rejected.length}
    <div class="rejected" transition:fade={{ duration: 200 }}>
      <span>Tanınmadı:</span>
      {#each station.rejected as token (token)}
        <code>{token}</code>
      {/each}
      <button class="mini" onclick={() => (station.rejected = [])}>gizle</button>
    </div>
  {/if}

  <div class="tools">
    <button class="btn" onclick={() => (station.matrixOpen = true)}>
      <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
        {#each [0, 1, 2] as row}
          {#each [0, 1, 2, 3] as col}
            <rect x={col * 4 + 0.5} y={row * 5 + 0.5} width="3" height="4" fill="currentColor" opacity={0.35 + ((row + col) % 3) * 0.25} />
          {/each}
        {/each}
      </svg>
      Matristen seç <span class="kbd">M</span>
    </button>
    <button
      class="btn"
      disabled={!station.selected.length || working}
      title="Benchmark'taki gürültülü rejim gibi: yaygınlığa göre seçilmiş, sorguya ait olmayan teknikler ekler"
      onclick={() => run(() => station.injectNoise(0.3))}
    >
      Gürültü enjekte et
    </button>
    <button class="btn" disabled={working} onclick={() => run(() => station.startBlind(0))}>Kör test</button>
    <button class="btn btn--ghost" disabled={working} onclick={() => run(() => station.startBlind(0.3))}>
      Gürültülü kör test
    </button>
  </div>

  <SignalTray />
  <SufficiencyGauge />
</Panel>

<style>
  .mini {
    font-family: var(--mono);
    font-size: 11.5px;
    letter-spacing: 0.08em;
    color: var(--ink-3);
    padding: 2px 6px;
    border: 1px solid var(--seam-2);
  }

  .mini:hover {
    color: var(--ink);
    border-color: var(--seam-3);
  }

  .tools {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 6px;
    margin-top: 14px;
  }

  .tools .btn {
    height: 32px;
    padding: 0 10px;
    font-size: 12.5px;
    justify-content: center;
  }

  .tools .btn--ghost {
    border-color: var(--seam-2);
  }

  .rejected {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px;
    margin-top: 10px;
    font-size: 12px;
    color: var(--ink-3);
  }

  .rejected code {
    font-family: var(--mono);
    font-size: 12px;
    color: var(--danger);
    border: 1px dashed rgba(255, 122, 107, 0.5);
    padding: 1px 5px;
  }
</style>
