<script>
  import { flip } from 'svelte/animate';
  import { fly, fade } from 'svelte/transition';
  import { backOut, cubicOut } from 'svelte/easing';
  import { prefersReducedMotion } from 'svelte/motion';
  import { station } from '../lib/station.svelte.js';
  import { heatColor, band, BAND_LABELS } from '../lib/format.js';

  const total = $derived(station.data?.dataset.actor_count ?? 0);
  const items = $derived(
    station.query
      .map((id) => {
        const t = station.techniques.get(id);
        return t ? { ...t, injected: station.noise.includes(id), band: band(t.actor_count, total) } : null;
      })
      .filter(Boolean)
      .sort((a, b) => b.heat - a.heat || a.id.localeCompare(b.id))
  );

  const heaviest = $derived(items.find((t) => !t.injected) ?? null);
  const lightest = $derived([...items].reverse().find((t) => !t.injected && t.band === 'common') ?? null);
  const motion = $derived(prefersReducedMotion.current ? 0 : 1);
</script>

<div class="tray">
  {#if items.length === 0}
    <div class="empty" in:fade={{ duration: 200 * motion }}>
      <div class="pulse" aria-hidden="true"></div>
      <p><strong>Sinyal bekleniyor.</strong> Gözlediğin teknikleri ara, bir listeyi yapıştır ya da matristen seç. Her teknik, ne kadar nadirse o kadar ağır iner.</p>
    </div>
  {:else}
    <ul aria-label="Gözlenen teknikler">
      {#each items as item (item.id)}
        <li
          class:heavy={item.band === 'distinctive'}
          class:light={item.band === 'common'}
          class:injected={item.injected}
          animate:flip={{ duration: 420 * motion, easing: cubicOut }}
          in:fly={{ y: -18, duration: (item.band === 'distinctive' ? 620 : 380) * motion, easing: backOut }}
          out:fade={{ duration: 160 * motion }}
          style:--heat={heatColor(item.heat)}
        >
          <span class="mass" style:height="{18 + item.heat * 22}px" aria-hidden="true"></span>
          <span class="id mono">{item.id}</span>
          <span class="name" title={item.name}>{item.name}</span>
          <span class="meta mono">
            {#if item.injected}<em>gürültü</em>{:else}<span class="band">{BAND_LABELS[item.band]} · </span>{/if}{#if item.injected} · {/if}{item.actor_count}
          </span>
          <button class="x" aria-label="{item.id} kaldır" onclick={() => station.remove(item.id)}>×</button>
        </li>
      {/each}
    </ul>

    {#if heaviest}
      <p class="insight" in:fade={{ duration: 300 * motion }}>
        En ağır sinyal <b class="mono" style:color={heatColor(heaviest.heat)}>{heaviest.id}</b>:
        yalnızca <b>{heaviest.actor_count}</b> aktörde raporlanmış.
        {#if lightest && lightest.id !== heaviest.id}
          <span class="cold"><b class="mono">{lightest.id}</b> ise {lightest.actor_count} aktörde — sonucu neredeyse hiç kıpırdatmaz.</span>
        {/if}
      </p>
    {/if}
  {/if}
</div>

<style>
  .tray {
    margin-top: 18px;
  }

  ul {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 4px;
  }

  li {
    position: relative;
    display: grid;
    grid-template-columns: 4px 58px 1fr auto 28px;
    align-items: center;
    gap: 10px;
    min-height: clamp(34px, 5.2vh, 42px);
    padding: 0 6px 0 0;
    background: var(--hull-2);
    border: 1px solid var(--seam);
  }

  li.heavy {
    border-color: color-mix(in oklab, var(--heat) 45%, var(--seam));
  }

  li.heavy::after {
    content: '';
    position: absolute;
    inset: -1px;
    border: 1px solid var(--heat);
    animation: impact 900ms var(--ease-out) both;
    pointer-events: none;
  }

  li.light {
    opacity: 0.72;
  }

  li.injected {
    border-style: dashed;
    background: transparent;
  }

  .mass {
    align-self: center;
    width: 4px;
    background: var(--heat);
    transition: height var(--t-slow) var(--ease-out);
  }

  .id {
    font-size: 13px;
    color: var(--heat);
  }

  .name {
    font-size: 13.5px;
    color: var(--ink);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .meta {
    font-size: 11.5px;
    color: var(--ink-3);
    white-space: nowrap;
  }

  .meta em {
    font-style: normal;
    color: var(--cold);
  }

  .x {
    width: 28px;
    height: 28px;
    color: var(--ink-3);
    font-size: 16px;
    line-height: 1;
  }

  .x:hover {
    color: var(--danger);
  }

  .insight {
    margin: 14px 0 0;
    font-size: 13px;
    line-height: 1.55;
    color: var(--ink-2);
  }

  .insight b {
    font-weight: 500;
    color: var(--ink);
  }

  .insight .cold {
    display: block;
    margin-top: 4px;
    color: var(--ink-3);
  }

  .insight .cold b {
    color: var(--cold);
  }

  .empty {
    display: grid;
    grid-template-columns: 28px 1fr;
    gap: 12px;
    align-items: start;
    padding: 16px;
    border: 1px dashed var(--seam-2);
  }

  .empty p {
    margin: 0;
    font-size: 13.5px;
    color: var(--ink-2);
  }

  .empty strong {
    color: var(--ink);
    font-weight: 500;
  }

  .pulse {
    width: 12px;
    height: 12px;
    margin: 5px 0 0 6px;
    border-radius: 50%;
    background: var(--signal);
    box-shadow: 0 0 0 0 rgba(255, 181, 74, 0.5);
    animation: beacon 2.4s var(--ease-out) infinite;
  }

  @container panel (max-width: 380px) {
    .band {
      display: none;
    }

    li {
      grid-template-columns: 4px 54px 1fr auto 28px;
      gap: 8px;
    }
  }

  @media (pointer: coarse) {
    .x {
      width: 40px;
      height: 40px;
    }

    li {
      grid-template-columns: 4px 58px 1fr auto 40px;
      min-height: 44px;
    }
  }

  @keyframes impact {
    0% {
      opacity: 1;
      transform: scale(1);
    }
    100% {
      opacity: 0;
      transform: scale(1.06, 1.35);
    }
  }

  @keyframes beacon {
    0% {
      box-shadow: 0 0 0 0 rgba(255, 181, 74, 0.5);
    }
    70% {
      box-shadow: 0 0 0 14px rgba(255, 181, 74, 0);
    }
    100% {
      box-shadow: 0 0 0 0 rgba(255, 181, 74, 0);
    }
  }
</style>
