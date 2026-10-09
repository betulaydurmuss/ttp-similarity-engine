<script>
  import { fly } from 'svelte/transition';
  import { prefersReducedMotion } from 'svelte/motion';
  import { cubicOut } from 'svelte/easing';
  import { station } from '../lib/station.svelte.js';
  import { pct, dec, int, LEVELS } from '../lib/format.js';

  const motion = $derived(prefersReducedMotion.current ? 0 : 1);
  const trust = $derived(station.trust);

  const regimes = [
    { id: 'A', title: 'Referans', body: 'Aktörün tekniklerinin yarısı, gürültüsüz. İstasyonun tavanı.' },
    { id: 'B', title: 'Seyrek', body: 'Yalnızca dörtte biri. Gerçek bir olayda çoğu zaman elde olan bu kadardır.' },
    { id: 'C', title: 'Gürültülü', body: 'Dörtte biri ve üstüne %30 yaygın, aktöre ait olmayan teknik. Gerçeğe en yakın sınav.' }
  ];
  const schemes = [
    ['smooth_idf', 'IDF ağırlıklı'],
    ['binary', 'ağırlıksız'],
    ['jaccard', 'Jaccard']
  ];

  function row(regime, scheme) {
    return trust?.summary?.find((r) => r.regime === regime && r.label === `${regime} / ${scheme}`);
  }

  const calibration = $derived(
    ['high', 'medium', 'low']
      .map((level) => trust?.calibration?.find((r) => r.regime === 'C' && r.label === 'C / smooth_idf' && r.confidence === level))
      .filter(Boolean)
  );
  const buckets = $derived(
    (trust?.by_size ?? []).filter((r) => r.regime === 'C' && r.label === 'C / smooth_idf')
  );
  const significance = $derived(trust?.significance?.find((r) => r.regime === 'C'));
</script>

<div class="trust scroll" in:fly={{ y: 24, duration: 520 * motion, easing: cubicOut }}>
  <header>
    <span class="eyebrow">Güven · ölçülmüş hâli</span>
    <h2>Bu istasyona ne kadar güvenebilirsin?</h2>
    <p>
      Bilinen her aktörün tekniklerinin bir kısmı saklanır, kalanı yeni bir olaymış gibi istasyona sorulur.
      Soru basit: doğru aktör kaçıncı sırada çıkıyor? Aynı tohumla aktör başına 20 deneme yapılır.
    </p>
  </header>

  {#if !trust}
    <p class="mono wait">ölçümler yükleniyor…</p>
  {:else if !trust.available}
    <div class="missing">
      <p>Bu veri seti için ölçüm henüz üretilmemiş. Depo kökünde şunu çalıştır, sonra sayfayı yenile:</p>
      <code>{trust.command}</code>
    </div>
  {:else}
    <section class="regimes">
      {#each regimes as regime, i}
        {@const main = row(regime.id, 'smooth_idf')}
        <article style:--i={i}>
          <span class="tag mono">Rejim {regime.id}</span>
          <h3>{regime.title}</h3>
          <p>{regime.body}</p>
          {#if main}
            <div class="figure">
              <span class="mono value">{pct(main.top1)}</span>
              <span class="caption">ilk sırada doğru</span>
            </div>
            <div class="minor mono">
              <span>ilk 3: {pct(main.top3)}</span>
              <span>ıska: {main.misses}</span>
              <span>{int(main.trials)} deneme</span>
            </div>
            <ul class="schemes">
              {#each schemes as [scheme, label]}
                {@const r = row(regime.id, scheme)}
                {#if r}
                  <li class:main={scheme === 'smooth_idf'}>
                    <span>{label}</span>
                    <span class="track"><i style:width="{r.top1 * 100}%"></i></span>
                    <span class="mono">{pct(r.top1, 1)}</span>
                  </li>
                {/if}
              {/each}
            </ul>
          {/if}
        </article>
      {/each}
    </section>

    {#if significance}
      <p class="note">
        Gürültülü rejimde IDF ağırlıklandırma, ağırlıksız sürümü {significance.better} aktörde geçiyor,
        {significance.worse} aktörde geride kalıyor (eşleştirilmiş Wilcoxon, p = {Number(significance.p_value).toExponential(1)}).
        Ağırlıklandırmanın değeri temiz sorguda değil, gürültüde ortaya çıkıyor.
      </p>
    {/if}

    <div class="split">
      {#if calibration.length}
        <section class="panel">
          <span class="eyebrow">Güven etiketi işe yarıyor mu? · rejim C</span>
          <ul class="bars">
            {#each calibration as c}
              <li class="lvl-{c.confidence}">
                <span class="lvl">{LEVELS[c.confidence].label}</span>
                <span class="track"><i style:width="{c.top1 * 100}%"></i></span>
                <span class="mono">{pct(c.top1)}</span>
                <span class="mono share">pay {pct(c.share)}</span>
              </li>
            {/each}
          </ul>
          <p>
            İstasyon “yüksek” dediğinde doğru aktör ilk sırada {pct(calibration[0]?.top1 ?? 0)} oranında;
            “düşük” dediğinde {pct(calibration[calibration.length - 1]?.top1 ?? 0)}. Güven etiketi süs değil, ölçülmüş bir uyarı.
          </p>
        </section>
      {/if}

      {#if buckets.length}
        <section class="panel">
          <span class="eyebrow">Dürüst zaaf: az belgelenen aktör · rejim C</span>
          <ul class="bars">
            {#each buckets as b}
              <li>
                <span class="lvl mono">{b.bucket}</span>
                <span class="track"><i style:width="{b.top1 * 100}%"></i></span>
                <span class="mono">{pct(b.top1)}</span>
                <span class="mono share">{int(b.actors)} aktör</span>
              </li>
            {/each}
          </ul>
          <p>
            Teknik sayısı arttıkça bulmak kolaylaşıyor. Benzerlik kısmen raporlama derinliğini de ölçüyor:
            az yazılmış bir aktör, gürültülü bir sorguda gözden kaçabilir.
            {#if !buckets.some((b) => b.bucket === '05-10')}
              12'den az tekniği olan aktörler bu rejimde hiç ölçülemiyor; dörtte biri 3 tekniğe ulaşmıyor.
            {/if}
          </p>
        </section>
      {/if}
    </div>

    <section class="limits">
      <span class="eyebrow">Sınırlar</span>
      <ul>
        <li>Sorgular, istasyonun indekslediği ATT&CK kayıtlarından çekilir; ölçülen şey erişim tutarlılığıdır, gerçek dünya faillik doğruluğu değil.</li>
        <li>ATT&CK kayıtları zaman damgası taşımaz; aktörlerin davranış değişimi modelde görünmez.</li>
        <li>Aynı araç setini kullanan farklı aktörler birbirine benzer görünür.</li>
      </ul>
    </section>
  {/if}

  <div class="cta">
    <button class="btn btn--signal" onclick={() => station.startBlind(0).catch((e) => station.notify(e.message))}>Kendin dene: kör test</button>
    <button class="btn" onclick={() => station.startBlind(0.3).catch((e) => station.notify(e.message))}>Gürültülü kör test</button>
  </div>
</div>

<style>
  .trust {
    height: 100%;
    padding: 28px 32px 40px;
    background: linear-gradient(180deg, rgba(10, 15, 23, 0.94), rgba(10, 15, 23, 0.98));
    border: 1px solid var(--seam);
  }

  header {
    max-width: 760px;
  }

  h2 {
    margin: 8px 0 8px;
    font-size: 36px;
    font-weight: 300;
    letter-spacing: -0.02em;
  }

  header p {
    margin: 0;
    color: var(--ink-2);
    font-size: 14.5px;
  }

  .regimes {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 1px;
    margin-top: 28px;
    background: var(--seam);
    border: 1px solid var(--seam);
  }

  article {
    background: var(--hull);
    padding: 20px;
    animation: rise var(--t-slow) var(--ease-out) both;
    animation-delay: calc(var(--i) * 120ms);
  }

  .tag {
    font-size: 11.5px;
    letter-spacing: 0.12em;
    color: var(--signal);
  }

  h3 {
    margin: 6px 0 4px;
    font-size: 19px;
    font-weight: 500;
  }

  article p {
    margin: 0;
    min-height: 44px;
    font-size: 13px;
    color: var(--ink-2);
  }

  .figure {
    display: flex;
    align-items: baseline;
    gap: 10px;
    margin-top: 16px;
  }

  .value {
    font-size: 44px;
    line-height: 1;
    color: var(--ink);
  }

  .caption {
    font-size: 12.5px;
    color: var(--ink-3);
  }

  .minor {
    display: flex;
    gap: 14px;
    margin-top: 8px;
    font-size: 12px;
    color: var(--ink-3);
  }

  .schemes,
  .bars {
    list-style: none;
    margin: 16px 0 0;
    padding: 0;
    display: grid;
    gap: 6px;
  }

  .schemes li {
    display: grid;
    grid-template-columns: 96px 1fr 48px;
    gap: 8px;
    align-items: center;
    font-size: 12.5px;
    color: var(--ink-3);
  }

  .schemes li.main {
    color: var(--ink);
  }

  .track {
    height: 5px;
    background: var(--seam);
  }

  .track i {
    display: block;
    height: 100%;
    background: var(--ink-3);
    animation: grow 900ms var(--ease-out) both;
    transform-origin: left;
  }

  .schemes li.main .track i {
    background: var(--signal);
  }

  .note {
    max-width: 860px;
    margin: 16px 0 0;
    font-size: 13.5px;
    color: var(--ink-2);
  }

  .split {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin-top: 24px;
  }

  .panel {
    padding: 18px 20px;
    border: 1px solid var(--seam);
    background: var(--hull);
  }

  .bars li {
    display: grid;
    grid-template-columns: 74px 1fr 48px 120px;
    gap: 10px;
    align-items: center;
    font-size: 13px;
  }

  .bars .share {
    font-size: 12px;
    color: var(--ink-3);
  }

  .lvl-high .track i {
    background: var(--lock);
  }

  .lvl-medium .track i {
    background: var(--signal);
  }

  .lvl-low .track i {
    background: var(--danger);
  }

  .panel p {
    margin: 14px 0 0;
    font-size: 13px;
    color: var(--ink-2);
  }

  .limits {
    margin-top: 24px;
  }

  .limits ul {
    margin: 10px 0 0;
    padding-left: 18px;
    color: var(--ink-2);
    font-size: 13.5px;
    display: grid;
    gap: 6px;
  }

  .cta {
    display: flex;
    gap: 8px;
    margin-top: 28px;
  }

  .missing code {
    display: inline-block;
    margin-top: 8px;
    padding: 8px 12px;
    font-family: var(--mono);
    font-size: 13px;
    background: var(--void);
    border: 1px solid var(--seam-2);
    color: var(--signal);
  }

  .wait {
    color: var(--ink-3);
  }

  @keyframes rise {
    from {
      opacity: 0;
      translate: 0 12px;
    }
  }

  @keyframes grow {
    from {
      transform: scaleX(0);
    }
  }

  @media (max-width: 1100px) {
    .regimes,
    .split {
      grid-template-columns: 1fr;
    }
  }
</style>
