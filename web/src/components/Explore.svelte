<script>
  import { flip } from 'svelte/animate';
  import { prefersReducedMotion } from 'svelte/motion';
  import { station } from '../lib/station.svelte.js';
  import { searchActors, matchedAlias } from '../lib/search.js';
  import { heatColor } from '../lib/format.js';
  import Panel from './Panel.svelte';

  let text = $state('');
  const motion = $derived(prefersReducedMotion.current ? 0 : 1);
  const actors = $derived(station.data?.actors ?? []);
  const found = $derived(searchActors(actors, text, 8));
  const constellations = $derived(
    [...(station.data?.constellations ?? [])].sort((a, b) => b.size - a.size || a.id - b.id)
  );
  const loners = $derived(actors.filter((a) => a.cluster < 0).length);

  function focus(id) {
    station.constellationFocus = station.constellationFocus === id ? null : id;
  }
</script>

<Panel
  index="01"
  kicker="Harita"
  title="Aktör uzayı"
  subtitle="Her nokta bir aktör; yakın duranlar benzer teknikler kullanır. Kesikli sınırlar, birlikte kümelenen takımyıldızlar."
>
  <label class="sr-only" for="actor-search">Aktör ara</label>
  <input
    id="actor-search"
    class="search mono"
    bind:value={text}
    placeholder="Aktör ara: APT29, Lazarus, G0016…"
    autocomplete="off"
    spellcheck="false"
  />
  {#if found.length}
    <ul class="found">
      {#each found as actor (actor.id)}
        {@const alias = matchedAlias(actor, text)}
        <li>
          <button onclick={() => station.openDossier(actor.id)} onpointerenter={() => (station.hover = actor.id)}>
            <span class="name">{actor.name}</span>
            <span class="mono id">{actor.id}</span>
            {#if alias}<span class="alias">↳ {alias}</span>{/if}
          </button>
        </li>
      {/each}
    </ul>
  {:else if text.trim()}
    <p class="none">Bu adla bir aktör yok.</p>
  {/if}

  <div class="head">
    <span class="eyebrow">Takımyıldızlar</span>
    <span class="mono count">{constellations.length} küme · {loners} tekil</span>
  </div>

  {#if station.constellationFocus !== null}
    <button class="clear mono" onclick={() => (station.constellationFocus = null)}>× odağı kaldır</button>
  {/if}

  <ul class="constellations">
    {#each constellations as c (c.id)}
      <li animate:flip={{ duration: 300 * motion }} class:on={station.constellationFocus === c.id}>
        <button onclick={() => focus(c.id)}>
          <span class="size mono">{c.size}</span>
          <span class="body">
            <span class="label">{c.label}</span>
            <span class="sig">
              {#each c.signature as s (s.id)}
                <span class="mono" style:color={heatColor(Math.min(1, s.lift / 10))}>{s.id}</span>
              {/each}
            </span>
            {#if station.constellationFocus === c.id}
              <span class="members">
                {c.members.map((id) => station.actors.get(id)?.name ?? id).join(', ')}
              </span>
            {/if}
          </span>
        </button>
      </li>
    {/each}
  </ul>
</Panel>

<style>
  .search {
    width: 100%;
    height: 44px;
    padding: 0 12px;
    background: var(--void);
    border: 1px solid var(--seam-2);
    font-size: 13.5px;
    outline: none;
  }

  .search:focus {
    border-color: var(--signal);
  }

  .found {
    list-style: none;
    margin: 6px 0 0;
    padding: 0;
    border: 1px solid var(--seam-2);
    background: var(--hull-2);
  }

  .found button {
    width: 100%;
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 2px 10px;
    padding: 8px 12px;
    text-align: left;
  }

  .found button:hover {
    background: var(--hull-3);
  }

  .found .name {
    font-size: 14px;
  }

  .found .id {
    font-size: 12px;
    color: var(--ink-3);
  }

  .found .alias {
    grid-column: 1 / -1;
    font-size: 12px;
    color: var(--signal);
  }

  .none {
    font-size: 13px;
    color: var(--ink-3);
  }

  .head {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin: 22px 0 10px;
  }

  .count {
    font-size: 12px;
    color: var(--ink-3);
  }

  .clear {
    font-size: 12px;
    color: var(--signal);
    margin-bottom: 8px;
  }

  .constellations {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 3px;
  }

  .constellations button {
    width: 100%;
    display: grid;
    grid-template-columns: 34px 1fr;
    gap: 10px;
    padding: 9px 10px;
    text-align: left;
    border: 1px solid transparent;
    transition: background var(--t-fast), border-color var(--t-fast);
  }

  .constellations button:hover {
    background: var(--hull-3);
  }

  li.on button {
    border-color: var(--signal-line);
    background: var(--signal-soft);
  }

  .size {
    font-size: 15px;
    color: var(--ink-2);
  }

  li.on .size {
    color: var(--signal);
  }

  .body {
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 3px;
  }

  .label {
    font-size: 13.5px;
    color: var(--ink);
  }

  .sig {
    display: flex;
    gap: 8px;
    font-size: 11.5px;
  }

  .members {
    margin-top: 4px;
    font-size: 12.5px;
    color: var(--ink-2);
    line-height: 1.5;
  }
</style>
