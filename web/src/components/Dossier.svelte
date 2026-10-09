<script>
  import { fly, fade } from 'svelte/transition';
  import { cubicOut } from 'svelte/easing';
  import { prefersReducedMotion } from 'svelte/motion';
  import { station } from '../lib/station.svelte.js';
  import { dec, heatColor, pct } from '../lib/format.js';
  import Panel from './Panel.svelte';

  const motion = $derived(prefersReducedMotion.current ? 0 : 1);
  const dossier = $derived(station.dossier);
  const candidate = $derived(
    dossier ? (station.result?.candidates ?? []).find((c) => c.id === dossier.id) ?? null : null
  );
  const queried = $derived(new Set(station.query));
  const constellation = $derived(dossier ? station.constellations.get(dossier.cluster.id) : null);
  const leader = $derived(station.result?.candidates?.[0] ?? null);
  const footprint = $derived(
    dossier
      ? (station.data?.tactics ?? [])
          .map((tactic) => ({
            ...tactic,
            items: dossier.techniques.filter((t) => t.tactics.includes(tactic.id))
          }))
      : []
  );

  function queryWithSignature() {
    const ids = dossier.techniques.slice(0, 6).map((t) => t.id);
    station.clear();
    station.add(ids);
    station.closeDossier();
    station.mode = 'observe';
    station.notify(`${dossier.name}: en ayırt edici 6 teknik sorguya kondu`);
  }
</script>

<div class="drawer" transition:fly={{ x: 40, duration: 460 * motion, easing: cubicOut }}>
  <Panel index="03" kicker="Aktör dosyası">
    {#snippet actions()}
      <button class="close" onclick={() => station.closeDossier()} aria-label="Dosyayı kapat">Kapat <span class="kbd">Esc</span></button>
    {/snippet}

    {#if station.dossierError}
      <p class="error">{station.dossierError}</p>
    {:else if !dossier}
      <div class="loading" aria-busy="true">
        <span></span><span></span><span></span>
      </div>
    {:else}
      {#key dossier.id}
        <div class="content" in:fade={{ duration: 260 * motion }}>
          <h2>{dossier.name}</h2>
          <p class="id mono">{dossier.id}</p>
          {#if dossier.aliases.length}
            <ul class="aliases">
              {#each dossier.aliases.slice(0, 10) as alias}<li>{alias}</li>{/each}
              {#if dossier.aliases.length > 10}<li class="more">+{dossier.aliases.length - 10}</li>{/if}
            </ul>
          {/if}

          <dl class="facts">
            <div><dt>teknik</dt><dd class="mono">{dossier.technique_count}</dd></div>
            <div><dt>ort. ağırlık</dt><dd class="mono">{dec(dossier.mean_weight)}</dd></div>
            <div>
              <dt>takımyıldız</dt>
              <dd>
                {#if constellation}
                  <button class="link" onclick={() => { station.mode = 'explore'; station.constellationFocus = constellation.id; }}>
                    {constellation.label}
                  </button>
                {:else}
                  <span class="muted">tekil</span>
                {/if}
              </dd>
            </div>
          </dl>

          {#if candidate}
            <section>
              <h4 class="eyebrow">Neden aday? <span class="mono">#{candidate.rank} · {dec(candidate.score, 3)}</span></h4>
              <ul class="evidence">
                {#each candidate.evidence as e, i (e.id)}
                  <li style:--i={i}>
                    <span class="mono eid" style:color={heatColor(station.techniques.get(e.id)?.heat ?? 0)}>{e.id}</span>
                    <span class="ename" title={e.name}>{e.name}</span>
                    <span class="ebar"><i style:width="{e.share * 100}%"></i></span>
                    <span class="mono eshare">{pct(e.share)}</span>
                  </li>
                {/each}
              </ul>
              {#if candidate.missing.length}
                <p class="missing">
                  <span>Bu aktörde raporlanmamış:</span>
                  {#each candidate.missing as id}<code>{id}</code>{/each}
                </p>
              {/if}
              {#if leader && leader.id !== dossier.id}
                <button class="btn compact" onclick={() => station.openComparison(leader.id, dossier.id)}>
                  1. aday {leader.name} ile karşılaştır
                </button>
              {/if}
            </section>
          {/if}

          <section>
            <h4 class="eyebrow">Taktik ayak izi</h4>
            <div class="footprint" role="list">
              {#each footprint as column (column.id)}
                <div class="col" role="listitem" title="{column.name}: {column.items.length} teknik">
                  <div class="cells">
                    {#each column.items as t (t.id)}
                      <span
                        class:hit={queried.has(t.id)}
                        style:background={heatColor(t.heat)}
                        title="{t.id} {t.name}"
                      ></span>
                    {/each}
                  </div>
                  <span class="cname">{column.name}</span>
                </div>
              {/each}
            </div>
            <p class="legend-note">Renk nadirliği gösterir; çerçeveli kareler senin gözleminde de var.</p>
          </section>

          <section>
            <h4 class="eyebrow">En ayırt edici teknikleri</h4>
            <ul class="techniques">
              {#each dossier.techniques.slice(0, 8) as t (t.id)}
                <li class:hit={queried.has(t.id)}>
                  <span class="mono" style:color={heatColor(t.heat)}>{t.id}</span>
                  <span class="tname" title={t.name}>{t.name}</span>
                  <span class="mono count">{t.actor_count} aktör</span>
                </li>
              {/each}
            </ul>
            <button class="btn compact" onclick={queryWithSignature}>Bu izlerle sorgula</button>
          </section>

          <section>
            <h4 class="eyebrow">En yakın komşular</h4>
            <ul class="neighbours">
              {#each dossier.neighbours as n (n.id)}
                <li>
                  <button class="nname" onclick={() => station.openDossier(n.id)} onpointerenter={() => (station.hover = n.id)}>
                    {n.name} <span class="mono">{n.id}</span>
                  </button>
                  <span class="nbar"><i style:width="{n.score * 100}%"></i></span>
                  <span class="mono nscore" title="benzerlik">{dec(n.score)}</span>
                  <span class="mono nshared" title="ortak teknik · ortak tekniklerin ortalama ağırlığı">{n.shared_count} · {dec(n.shared_mean_weight, 1)}</span>
                  <button class="cmp" onclick={() => station.openComparison(dossier.id, n.id)} aria-label="{n.name} ile karşılaştır">⇄</button>
                </li>
              {/each}
            </ul>
            <p class="legend-note">Ortak tekniklerin ortalama ağırlığı yüksekse benzerlik nadir davranıştan, düşükse herkesin yaptığından gelir.</p>
          </section>
        </div>
      {/key}
    {/if}
  </Panel>
</div>

<style>
  .drawer {
    height: 100%;
    display: flex;
    flex-direction: column;
  }

  .drawer :global(.panel) {
    height: 100%;
  }

  .close {
    font-size: 12px;
    color: var(--ink-3);
    display: inline-flex;
    gap: 6px;
    align-items: center;
  }

  .close:hover {
    color: var(--ink);
  }

  h2 {
    margin: 0;
    font-size: 30px;
    font-weight: 400;
    letter-spacing: -0.02em;
    line-height: 1.1;
  }

  .id {
    margin: 4px 0 10px;
    font-size: 12.5px;
    color: var(--ink-3);
  }

  .aliases {
    list-style: none;
    margin: 0 0 14px;
    padding: 0;
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
  }

  .aliases li {
    font-size: 12px;
    padding: 2px 7px;
    border: 1px solid var(--seam-2);
    color: var(--ink-2);
  }

  .aliases .more {
    color: var(--ink-3);
  }

  .facts {
    display: grid;
    grid-template-columns: auto auto 1fr;
    gap: 18px;
    margin: 0 0 6px;
    padding: 12px 0;
    border-top: 1px solid var(--seam);
    border-bottom: 1px solid var(--seam);
  }

  .facts dt {
    font-size: 11.5px;
    color: var(--ink-3);
  }

  .facts dd {
    margin: 2px 0 0;
    font-size: 15px;
  }

  .link {
    font-size: 13px;
    color: var(--signal);
    text-align: left;
    text-decoration: underline;
    text-decoration-color: var(--signal-line);
    text-underline-offset: 3px;
  }

  .muted {
    color: var(--ink-3);
    font-size: 13px;
  }

  section {
    margin-top: 20px;
  }

  h4 {
    margin: 0 0 10px;
    font-weight: 400;
    display: flex;
    justify-content: space-between;
  }

  h4 .mono {
    color: var(--signal);
    letter-spacing: 0;
  }

  .evidence,
  .techniques,
  .neighbours {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 6px;
  }

  .evidence li {
    display: grid;
    grid-template-columns: 52px 1fr 70px 38px;
    gap: 8px;
    align-items: center;
    font-size: 13px;
    animation: slide var(--t-slow) var(--ease-out) both;
    animation-delay: calc(var(--i) * 50ms);
  }

  .eid {
    font-size: 12.5px;
  }

  .ename,
  .tname {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    color: var(--ink);
  }

  .ebar,
  .nbar {
    height: 4px;
    background: var(--seam);
  }

  .ebar i {
    display: block;
    height: 100%;
    background: var(--signal);
  }

  .eshare {
    font-size: 12px;
    text-align: right;
  }

  .missing {
    display: flex;
    flex-wrap: wrap;
    gap: 5px;
    align-items: center;
    margin: 12px 0 0;
    font-size: 12px;
    color: var(--ink-3);
  }

  .missing code {
    font-family: var(--mono);
    font-size: 11.5px;
    border: 1px dashed var(--seam-3);
    padding: 1px 5px;
    color: var(--ink-2);
  }

  .compact {
    margin-top: 12px;
    height: 32px;
    font-size: 12.5px;
  }

  .footprint {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(22px, 1fr));
    gap: 3px;
    align-items: end;
  }

  .col {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
  }

  .cells {
    display: flex;
    flex-direction: column-reverse;
    gap: 2px;
    min-height: 60px;
    justify-content: flex-start;
  }

  .cells span {
    width: 14px;
    height: 6px;
    opacity: 0.9;
  }

  .cells span.hit {
    outline: 1.5px solid var(--ink);
    outline-offset: 1px;
  }

  .cname {
    writing-mode: vertical-rl;
    transform: rotate(180deg);
    font-size: 10.5px;
    color: var(--ink-3);
    max-height: 92px;
    overflow: hidden;
    white-space: nowrap;
  }

  .legend-note {
    margin: 8px 0 0;
    font-size: 12px;
    color: var(--ink-3);
  }

  .techniques li {
    display: grid;
    grid-template-columns: 52px 1fr auto;
    gap: 8px;
    font-size: 13px;
    padding: 2px 0;
  }

  .techniques li.hit {
    box-shadow: inset 2px 0 0 var(--signal);
    padding-left: 6px;
  }

  .count {
    font-size: 11.5px;
    color: var(--ink-3);
  }

  .neighbours li {
    display: grid;
    grid-template-columns: 1fr 60px 38px 54px 22px;
    gap: 8px;
    align-items: center;
  }

  .nname {
    text-align: left;
    font-size: 13.5px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .nname .mono {
    font-size: 11px;
    color: var(--ink-3);
    margin-left: 4px;
  }

  .nname:hover {
    color: var(--signal);
  }

  .nbar i {
    display: block;
    height: 100%;
    background: var(--ink-3);
  }

  .nscore,
  .nshared {
    font-size: 12px;
    text-align: right;
    color: var(--ink-2);
  }

  .nshared {
    color: var(--ink-3);
  }

  .cmp {
    color: var(--ink-3);
    font-size: 15px;
  }

  .cmp:hover {
    color: var(--signal);
  }

  .error {
    color: var(--danger);
  }

  .loading {
    display: grid;
    gap: 10px;
  }

  .loading span {
    height: 14px;
    background: linear-gradient(90deg, var(--seam) 0%, var(--seam-2) 50%, var(--seam) 100%);
    background-size: 200% 100%;
    animation: shimmer 1.2s linear infinite;
  }

  .loading span:nth-child(1) {
    width: 60%;
    height: 28px;
  }

  @keyframes shimmer {
    to {
      background-position: -200% 0;
    }
  }

  @keyframes slide {
    from {
      opacity: 0;
      translate: 8px 0;
    }
  }
</style>
