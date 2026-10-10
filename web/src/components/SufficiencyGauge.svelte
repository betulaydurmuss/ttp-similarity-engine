<script>
  import { station } from '../lib/station.svelte.js';

  const minimum = $derived(station.data?.scoring.min_query_techniques ?? 3);
  const saturation = $derived(station.data?.scoring.sufficiency_saturation ?? 12);
  const count = $derived(station.query.length);
  const segments = $derived(Array.from({ length: saturation }, (_, i) => i + 1));
  const message = $derived(
    count === 0
      ? `En az ${minimum} teknik gerekli; ${saturation} teknikte yeterlilik tam dolar.`
      : count < minimum
        ? `${minimum - count} teknik daha ekle: ${minimum} teknikten azıyla güven her durumda DÜŞÜK kalır.`
        : count >= saturation
          ? 'Yeterlilik tam. Bundan sonrası güveni bu bileşenden artırmaz.'
          : `Yeterlilik %${Math.round(((count - minimum) / (saturation - minimum)) * 100)} — her yeni teknik kararı güçlendirir.`
  );
</script>

<div class="gauge" aria-live="polite">
  <div class="head">
    <span class="eyebrow">Gözlem yeterliliği</span>
    <span class="mono count">{Math.min(count, 99)}<span>/{saturation}</span></span>
  </div>
  <div class="cells" aria-hidden="true" style:--n={saturation}>
    {#each segments as n}
      <span class:on={n <= count} class:below={n <= minimum} style:--i={n}></span>
    {/each}
  </div>
  <p>{message}</p>
</div>

<style>
  .gauge {
    margin-top: 20px;
    padding-top: 16px;
    border-top: 1px solid var(--seam);
  }

  .head {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
  }

  .count {
    font-size: 15px;
    color: var(--ink);
  }

  .count span {
    color: var(--ink-3);
  }

  .cells {
    display: grid;
    grid-template-columns: repeat(var(--n), 1fr);
    gap: 3px;
    margin: 10px 0 8px;
  }

  .cells span {
    height: 8px;
    background: var(--seam);
    transition: background var(--t-base) var(--ease-out) calc(var(--i) * 18ms);
  }

  .cells span.below {
    background: rgba(255, 122, 107, 0.16);
  }

  .cells span.on {
    background: var(--signal);
  }

  .cells span.on.below {
    background: var(--danger);
  }

  p {
    margin: 0;
    font-size: 12.5px;
    color: var(--ink-2);
  }
</style>
