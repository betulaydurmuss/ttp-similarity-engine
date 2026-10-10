<script>
  import { fade, fly } from 'svelte/transition';
  import { prefersReducedMotion } from 'svelte/motion';
  import { station } from '../lib/station.svelte.js';
  import { dec, heatColor, pct } from '../lib/format.js';

  const motion = $derived(prefersReducedMotion.current ? 0 : 1);
  const data = $derived(station.comparison?.data);
  const sharedHeat = $derived(
    data?.shared.length ? data.shared.reduce((sum, t) => sum + t.heat, 0) / data.shared.length : 0
  );

  function close() {
    station.comparison = null;
  }
</script>

<div class="backdrop" transition:fade={{ duration: 200 * motion }} onclick={close} role="presentation"></div>
<div
  class="compare"
  role="dialog"
  aria-modal="true"
  aria-label="Aktör karşılaştırması"
  tabindex="-1"
  transition:fly={{ y: 20, duration: 420 * motion }}
  onkeydown={(event) => event.key === 'Escape' && close()}
>
  {#if !data}
    <p class="wait mono">karşılaştırılıyor…</p>
  {:else}
    <header>
      <button class="side left" onclick={() => { station.openDossier(data.left.id); close(); }}>
        <span class="eyebrow">A</span>
        <strong>{data.left.name}</strong>
        <span class="mono">{data.left.id} · {data.left.technique_count} teknik</span>
      </button>
      <div class="score">
        <span class="mono big">{dec(data.similarity)}</span>
        <span class="eyebrow">kosinüs benzerliği</span>
        <span class="mono small">Jaccard {dec(data.jaccard)} · ortak {data.shared.length}</span>
      </div>
      <button class="side right" onclick={() => { station.openDossier(data.right.id); close(); }}>
        <span class="eyebrow">B</span>
        <strong>{data.right.name}</strong>
        <span class="mono">{data.right.id} · {data.right.technique_count} teknik</span>
      </button>
      <button class="x" onclick={close} aria-label="Kapat">×</button>
    </header>

    <p class="read">
      {#if data.shared.length === 0}
        Bu iki aktörün raporlanmış ortak tekniği yok.
      {:else if sharedHeat >= 0.5}
        Ortak tekniklerin ortalama nadirliği <b>{pct(sharedHeat)}</b>: benzerlik, az görülen davranışlardan geliyor.
      {:else}
        Ortak tekniklerin ortalama nadirliği <b>{pct(sharedHeat)}</b>: benzerliğin çoğu, herkesin yaptığı davranışlardan.
      {/if}
    </p>

    <div class="columns scroll">
      {#each [['Yalnız A', data.left_only], ['Ortak', data.shared], ['Yalnız B', data.right_only]] as [title, rows], ci}
        <section class:shared={ci === 1}>
          <h3>{title} <span class="mono">{rows.length}</span></h3>
          <ul>
            {#each rows as t, i (t.id)}
              <li style:--i={Math.min(i, 20)}>
                <span class="mono" style:color={heatColor(t.heat)}>{t.id}</span>
                <span class="name" title={t.name}>{t.name}</span>
                <span class="heat" style:background={heatColor(t.heat)} style:width="{8 + t.heat * 30}px"></span>
              </li>
            {/each}
          </ul>
        </section>
      {/each}
    </div>
  {/if}
</div>

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    z-index: 42;
    background: rgba(4, 6, 10, 0.72);
  }

  .compare {
    position: fixed;
    z-index: 43;
    top: 88px;
    left: 50%;
    width: min(1040px, calc(100vw - 32px));
    max-height: calc(100vh - 120px);
    transform: translateX(-50%);
    display: flex;
    flex-direction: column;
    background: var(--hull);
    border: 1px solid var(--seam-2);
    box-shadow: 0 30px 80px -20px rgba(0, 0, 0, 0.9);
  }

  header {
    position: relative;
    display: grid;
    grid-template-columns: 1fr auto 1fr;
    gap: 20px;
    align-items: center;
    padding: 22px 24px;
    border-bottom: 1px solid var(--seam);
  }

  .side {
    display: flex;
    flex-direction: column;
    gap: 2px;
    text-align: left;
  }

  .side.right {
    text-align: right;
    align-items: flex-end;
  }

  .side strong {
    font-size: 24px;
    font-weight: 400;
  }

  .side .mono {
    font-size: 12px;
    color: var(--ink-3);
  }

  .side:hover strong {
    color: var(--signal);
  }

  .score {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
    padding: 0 20px;
    border-left: 1px solid var(--seam);
    border-right: 1px solid var(--seam);
  }

  .big {
    font-size: 38px;
    color: var(--signal);
    line-height: 1;
  }

  .small {
    font-size: 12px;
    color: var(--ink-3);
  }

  .x {
    position: absolute;
    top: 8px;
    right: 12px;
    font-size: 20px;
    color: var(--ink-3);
  }

  .read {
    margin: 0;
    padding: 12px 24px;
    font-size: 13.5px;
    color: var(--ink-2);
    border-bottom: 1px solid var(--seam);
  }

  .read b {
    color: var(--signal);
    font-weight: 500;
  }

  .columns {
    display: grid;
    grid-template-columns: 1fr 1.15fr 1fr;
    gap: 1px;
    background: var(--seam);
    overflow: auto;
  }

  section {
    background: var(--hull);
    padding: 14px 16px;
  }

  section.shared {
    background: var(--hull-2);
  }

  h3 {
    margin: 0 0 10px;
    font-size: 13px;
    font-weight: 600;
    display: flex;
    justify-content: space-between;
  }

  h3 .mono {
    color: var(--ink-3);
    font-weight: 400;
  }

  ul {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 4px;
  }

  li {
    display: grid;
    grid-template-columns: 50px 1fr auto;
    gap: 8px;
    align-items: center;
    font-size: 12.5px;
    animation: rise var(--t-base) var(--ease-out) both;
    animation-delay: calc(var(--i) * 18ms);
  }

  li .mono {
    font-size: 12px;
  }

  .name {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    color: var(--ink-2);
  }

  .heat {
    height: 4px;
  }

  .wait {
    padding: 40px;
    text-align: center;
    color: var(--ink-3);
  }

  @keyframes rise {
    from {
      opacity: 0;
      translate: 0 4px;
    }
  }

  @media (max-width: 860px) {
    header {
      grid-template-columns: 1fr;
    }
    .side.right {
      text-align: left;
      align-items: flex-start;
    }
    .score {
      border: 0;
      align-items: flex-start;
      padding: 0;
    }
    .columns {
      grid-template-columns: 1fr;
    }
  }
</style>
