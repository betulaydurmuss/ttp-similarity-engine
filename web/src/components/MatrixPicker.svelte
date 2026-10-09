<script>
  import { fade, fly } from 'svelte/transition';
  import { prefersReducedMotion } from 'svelte/motion';
  import { station } from '../lib/station.svelte.js';
  import { heatColor } from '../lib/format.js';

  let filter = $state('');
  let dialog;

  const motion = $derived(prefersReducedMotion.current ? 0 : 1);
  const chosen = $derived(new Set(station.query));
  const needle = $derived(filter.trim().toLocaleLowerCase('tr'));
  const columns = $derived(
    (station.data?.tactics ?? []).map((tactic) => ({
      ...tactic,
      techniques: (station.data?.techniques ?? [])
        .filter((t) => t.tactics.includes(tactic.id))
        .sort((a, b) => b.heat - a.heat || a.id.localeCompare(b.id))
    }))
  );

  function matches(t) {
    if (!needle) return true;
    return t.id.toLowerCase().includes(needle) || t.name.toLocaleLowerCase('tr').includes(needle);
  }

  function close() {
    station.matrixOpen = false;
  }

  $effect(() => {
    dialog?.querySelector('input')?.focus();
  });
</script>

<div class="backdrop" transition:fade={{ duration: 220 * motion }} onclick={close} role="presentation"></div>
<div
  class="matrix"
  bind:this={dialog}
  role="dialog"
  aria-modal="true"
  aria-label="ATT&CK matrisi"
  tabindex="-1"
  transition:fly={{ y: 24, duration: 420 * motion }}
  onkeydown={(event) => event.key === 'Escape' && close()}
>
  <header>
    <div>
      <span class="eyebrow">ATT&CK matrisi · {station.data?.dataset.technique_count} teknik</span>
      <h2>Gözlediğin davranışı işaretle</h2>
      <p>Her sütun bir taktik. Teknikler nadirden yaygına doğru dizildi: üstteki sıcak hücreler ayırt edici, alttaki soğuk hücreler herkeste var.</p>
    </div>
    <div class="tools">
      <input bind:value={filter} placeholder="Süz: kimlik ya da ad" aria-label="Matrisi süz" />
      <div class="legend" aria-hidden="true">
        <span>yaygın</span>
        <i></i>
        <span>nadir</span>
      </div>
      <span class="mono picked">{chosen.size} seçili</span>
      <button class="btn btn--signal" onclick={close}>Tamam <span class="kbd">Esc</span></button>
    </div>
  </header>

  <div class="grid scroll">
    {#each columns as column, ci (column.id)}
      <section class="column" style:--ci={ci}>
        <h3 title={column.name_en}>
          {column.name}
          <span class="mono">{column.techniques.length}</span>
        </h3>
        {#each column.techniques as t (t.id)}
          <button
            class="cell"
            class:on={chosen.has(t.id)}
            class:muted={!matches(t)}
            style:--heat={heatColor(t.heat)}
            title="{t.id} {t.name} — {t.actor_count} aktörde"
            aria-pressed={chosen.has(t.id)}
            onclick={() => station.toggle(t.id)}
          >
            <span class="mono">{t.id}</span>
            <span class="label">{t.name}</span>
          </button>
        {/each}
      </section>
    {/each}
  </div>
</div>

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    z-index: 40;
    background: rgba(4, 6, 10, 0.72);
    backdrop-filter: blur(2px);
  }

  .matrix {
    position: fixed;
    z-index: 41;
    inset: 76px 24px 24px;
    display: flex;
    flex-direction: column;
    background: var(--hull);
    border: 1px solid var(--seam-2);
    box-shadow: 0 30px 80px -20px rgba(0, 0, 0, 0.9);
  }

  header {
    display: flex;
    justify-content: space-between;
    gap: 24px;
    align-items: flex-end;
    padding: 20px 24px 16px;
    border-bottom: 1px solid var(--seam);
  }

  h2 {
    margin: 6px 0 4px;
    font-size: 22px;
    font-weight: 400;
  }

  header p {
    margin: 0;
    font-size: 13px;
    color: var(--ink-2);
    max-width: 70ch;
  }

  .tools {
    display: flex;
    align-items: center;
    gap: 14px;
    flex-shrink: 0;
  }

  .tools input {
    height: 36px;
    width: 200px;
    padding: 0 10px;
    background: var(--void);
    border: 1px solid var(--seam-2);
    font-family: var(--mono);
    font-size: 13px;
  }

  .legend {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    color: var(--ink-3);
  }

  .legend i {
    width: 72px;
    height: 6px;
    background: linear-gradient(90deg, rgb(75, 95, 124), rgb(154, 170, 191) 45%, rgb(255, 181, 74) 78%, rgb(255, 123, 58));
  }

  .picked {
    font-size: 12.5px;
    color: var(--signal);
  }

  .grid {
    flex: 1;
    display: grid;
    grid-auto-flow: column;
    grid-auto-columns: minmax(138px, 1fr);
    gap: 6px;
    padding: 14px 16px 18px;
    overflow: auto;
    align-items: start;
  }

  .column {
    display: grid;
    gap: 3px;
    animation: rise var(--t-slow) var(--ease-out) both;
    animation-delay: calc(var(--ci) * 28ms);
  }

  h3 {
    position: sticky;
    top: -14px;
    z-index: 1;
    margin: 0 0 4px;
    padding: 8px 6px;
    background: var(--hull);
    border-bottom: 1px solid var(--seam-2);
    font-size: 12.5px;
    font-weight: 600;
    color: var(--ink);
    display: flex;
    justify-content: space-between;
    gap: 6px;
  }

  h3 .mono {
    color: var(--ink-3);
    font-weight: 400;
  }

  .cell {
    display: flex;
    flex-direction: column;
    gap: 1px;
    text-align: left;
    padding: 6px 7px;
    min-height: 44px;
    background: color-mix(in oklab, var(--heat) 9%, var(--hull-2));
    border: 1px solid transparent;
    border-left: 3px solid var(--heat);
    transition: background var(--t-fast), border-color var(--t-fast), opacity var(--t-fast), transform var(--t-fast);
  }

  .cell:hover {
    border-color: var(--seam-3);
    border-left-color: var(--heat);
  }

  .cell .mono {
    font-size: 11.5px;
    color: var(--heat);
  }

  .label {
    font-size: 12px;
    line-height: 1.25;
    color: var(--ink-2);
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .cell.on {
    background: var(--signal);
    border-left-color: var(--signal-hot);
    animation: pick var(--t-base) var(--ease-out);
  }

  .cell.on .mono,
  .cell.on .label {
    color: var(--void);
  }

  .cell.muted {
    opacity: 0.16;
  }

  @keyframes rise {
    from {
      opacity: 0;
      translate: 0 10px;
    }
  }

  @keyframes pick {
    50% {
      transform: scale(0.96);
    }
  }

  @media (max-width: 860px) {
    .matrix {
      inset: 8px;
    }
    header {
      flex-direction: column;
      align-items: stretch;
    }
    .tools {
      flex-wrap: wrap;
    }
  }
</style>
