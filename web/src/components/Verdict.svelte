<script>
  import { fade, fly, scale } from 'svelte/transition';
  import { prefersReducedMotion } from 'svelte/motion';
  import { cubicOut, backOut } from 'svelte/easing';
  import { station } from '../lib/station.svelte.js';
  import { navigatorLayer, resultDocument, markdownSummary, download } from '../lib/exporters.js';
  import Panel from './Panel.svelte';
  import ConfidenceDial from './ConfidenceDial.svelte';
  import CandidateList from './CandidateList.svelte';

  const motion = $derived(prefersReducedMotion.current ? 0 : 1);
  const result = $derived(station.result);
  const top = $derived(result?.candidates?.[0] ?? null);
  const level = $derived(result?.confidence.level ?? 'low');
  const blindRank = $derived(
    station.blind && result ? (result.candidates.find((c) => c.id === station.blind.answer.id)?.rank ?? null) : null
  );

  async function copy(text, message) {
    try {
      await navigator.clipboard.writeText(text);
      station.notify(message);
    } catch {
      station.notify('Panoya erişilemedi');
    }
  }

  function exportLayer() {
    download('istasyon-navigator-katmani.json', navigatorLayer({ result, techniques: station.data.techniques, dataset: station.data.dataset }));
  }

  function exportJson() {
    download('istasyon-sonuc.json', resultDocument({ result, dataset: station.data.dataset }));
  }
</script>

<Panel index="02" kicker="Yörünge" title={top ? 'En yakın davranış' : 'Sonuç'}>
  {#snippet actions()}
    {#if station.busy}
      <span class="scanning mono" transition:fade={{ duration: 150 }}>tarıyor</span>
    {/if}
  {/snippet}

  {#if !result || !result.candidates.length}
    <div class="idle" in:fade={{ duration: 240 * motion }}>
      {#if result && result.query.known.length}
        <p class="lead">Bu teknik setiyle eşleşen bir aktör yok.</p>
      {:else}
        <p class="lead">Gözlemin uzaya düştüğünde burada okunacak.</p>
      {/if}
      <ol class="steps">
        <li><span class="mono">01</span> Teknikleri ekle; her biri nadirliği kadar ağırlık taşır.</li>
        <li><span class="mono">02</span> İstasyon gözlemi aktör uzayına yerleştirir ve en yakın komşuları sıralar.</li>
        <li><span class="mono">03</span> Güven; nadirlik, ayrışma ve yeterlilikten ölçülür ve açıkça gösterilir.</li>
      </ol>
      <button class="btn btn--signal" onclick={() => station.startBlind(0).catch((e) => station.notify(e.message))}>
        Kör testle dene
      </button>
    </div>
  {:else}
    {#if station.blind}
      <div class="blind" class:revealed={station.blind.revealed}>
        {#if !station.blind.revealed}
          <p>Gizli aktör listede mi? Sıralamaya bak, sonra cevabı aç.</p>
          <button class="btn" onclick={() => station.revealBlind()}>Cevabı göster</button>
        {:else}
          <div class="reveal" in:scale={{ start: 0.92, duration: 520 * motion, easing: backOut }}>
            <span class="ring" class:hit={blindRank === 1} aria-hidden="true"></span>
            <div>
              <span class="eyebrow">gizli aktör</span>
              <strong>{station.blind.answer.name} <span class="mono">{station.blind.answer.id}</span></strong>
              <p>
                {#if blindRank === 1}
                  İstasyon onu birinci sırada buldu.
                {:else if blindRank}
                  İstasyon onu {blindRank}. sırada buldu.
                {:else}
                  İlk {result.candidates.length} aday arasında yok — istasyon bu kez kaçırdı.
                {/if}
              </p>
            </div>
          </div>
        {/if}
      </div>
    {/if}

    {#key top.id}
      <div class="headline" in:fly={{ y: 10, duration: 480 * motion, easing: cubicOut }}>
        {#if level === 'high'}
          <p>Gözlenen davranış en çok</p>
          <h3>{top.name}</h3>
          <p>ile benzeşiyor.</p>
        {:else if level === 'medium'}
          <p>Gözlenen davranış</p>
          <h3>{top.name}</h3>
          <p>ile benzeşiyor, ama alternatifler de yakın.</p>
        {:else}
          <p>En yakın aday</p>
          <h3>{top.name}</h3>
          <p>ama bu sinyal bir karar için zayıf.</p>
        {/if}
        <p class="fine">
          <span class="mono">{top.id}</span>
          {#if top.aliases.length}· {top.aliases.slice(0, 3).join(', ')}{/if}
        </p>
        <p class="principle">Bu bir faillik tespiti değil; raporlanmış tekniklerin örtüşmesi.</p>
      </div>
    {/key}

    <section class="block">
      <span class="eyebrow">Güven</span>
      <ConfidenceDial confidence={result.confidence} />
    </section>

    <section class="block">
      <div class="block-head">
        <span class="eyebrow">Adaylar</span>
        <span class="hint">satıra tıkla: aktör dosyası</span>
      </div>
      <CandidateList {result} />
    </section>

    <section class="block share">
      <span class="eyebrow">Paylaş ve dışa aktar</span>
      <div class="share-row">
        <button class="btn" onclick={() => copy(location.href, 'Bağlantı kopyalandı')}>Bağlantı</button>
        <button class="btn" onclick={() => copy(markdownSummary({ result, dataset: station.data.dataset }), 'Özet panoya kopyalandı')}>Özet (Markdown)</button>
        <button class="btn" onclick={exportLayer}>Navigator katmanı</button>
        <button class="btn" onclick={exportJson}>JSON</button>
      </div>
    </section>
  {/if}
</Panel>

<style>
  .scanning {
    font-size: 11px;
    letter-spacing: 0.14em;
    color: var(--signal);
    animation: blink 900ms steps(2) infinite;
  }

  .idle .lead {
    margin: 4px 0 14px;
    font-size: 17px;
    font-weight: 300;
    color: var(--ink);
  }

  .steps {
    list-style: none;
    padding: 0;
    margin: 0 0 18px;
    display: grid;
    gap: 10px;
  }

  .steps li {
    display: grid;
    grid-template-columns: 28px 1fr;
    font-size: 13.5px;
    color: var(--ink-2);
  }

  .steps .mono {
    color: var(--signal);
    font-size: 12px;
    padding-top: 2px;
  }

  .headline {
    padding-bottom: 16px;
  }

  .headline p {
    margin: 0;
    font-size: 15px;
    font-weight: 300;
    color: var(--ink-2);
  }

  .headline h3 {
    margin: 2px 0;
    font-size: 34px;
    font-weight: 400;
    letter-spacing: -0.02em;
    line-height: 1.1;
    color: var(--ink);
  }

  .headline .fine {
    margin-top: 8px;
    font-size: 12.5px;
    color: var(--ink-3);
  }

  .headline .principle {
    margin-top: 10px;
    font-size: 12.5px;
    color: var(--signal);
    opacity: 0.9;
  }

  .block {
    padding: 16px 0 4px;
    border-top: 1px solid var(--seam);
  }

  .block .eyebrow {
    display: block;
    margin-bottom: 12px;
  }

  .block-head {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
  }

  .hint {
    font-size: 12px;
    color: var(--ink-3);
  }

  .share-row {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }

  .share-row .btn {
    height: 32px;
    font-size: 12.5px;
    padding: 0 10px;
  }

  .blind {
    margin-bottom: 16px;
    padding: 12px 14px;
    border: 1px dashed var(--lock);
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }

  .blind p {
    margin: 0;
    font-size: 13px;
    color: var(--ink-2);
  }

  .blind.revealed {
    border-style: solid;
    background: rgba(127, 224, 195, 0.06);
  }

  .reveal {
    display: grid;
    grid-template-columns: 34px 1fr;
    gap: 12px;
    align-items: center;
  }

  .reveal strong {
    display: block;
    font-size: 17px;
    font-weight: 500;
  }

  .reveal strong .mono {
    font-size: 12px;
    color: var(--ink-3);
    font-weight: 400;
  }

  .ring {
    width: 30px;
    height: 30px;
    border-radius: 50%;
    border: 2px solid var(--danger);
    position: relative;
  }

  .ring.hit {
    border-color: var(--lock);
    animation: lock 900ms var(--ease-out) both;
  }

  .ring.hit::after {
    content: '';
    position: absolute;
    inset: 7px;
    border-radius: 50%;
    background: var(--lock);
  }

  @media (max-height: 820px) {
    .headline h3 {
      font-size: 28px;
    }

    .headline {
      padding-bottom: 10px;
    }

    .block {
      padding-top: 12px;
    }
  }

  @keyframes lock {
    0% {
      box-shadow: 0 0 0 0 rgba(127, 224, 195, 0.6);
      transform: rotate(-90deg) scale(0.6);
    }
    100% {
      box-shadow: 0 0 0 14px rgba(127, 224, 195, 0);
      transform: rotate(0) scale(1);
    }
  }

  @keyframes blink {
    50% {
      opacity: 0.35;
    }
  }
</style>
