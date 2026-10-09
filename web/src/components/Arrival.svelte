<script>
  import { onMount, untrack } from 'svelte';
  import { Tween, prefersReducedMotion } from 'svelte/motion';
  import { cubicOut } from 'svelte/easing';
  import { fade } from 'svelte/transition';
  import { int } from '../lib/format.js';

  let { data, quick = false, onchoose } = $props();

  let phase = $state(0);
  const instant = untrack(() => quick) || prefersReducedMotion.current;
  const actors = new Tween(0, { duration: instant ? 0 : 1500, easing: cubicOut });
  const techniques = new Tween(0, { duration: instant ? 0 : 1500, easing: cubicOut });
  const edges = new Tween(0, { duration: instant ? 0 : 1700, easing: cubicOut });

  const principles = [
    ['Nadir davranış iz bırakır.', 'Herkesin kullandığı teknik kimseyi işaret etmez. Az görülen teknik ise aktörü ele verir; istasyon ağırlığı buradan alır.'],
    ['Benzerlik bir mesafedir.', 'Her aktör, raporlanmış tekniklerinin oluşturduğu uzayda bir noktadır. Gözlemin bu uzaya düşer ve en yakın komşularını arar.'],
    ['Benzerlik, faillik değildir.', '“Bu odur” denmez. “En çok buna benziyor” denir ve ne kadar emin olunduğu açıkça söylenir.']
  ];

  onMount(() => {
    const steps = instant ? [0, 0, 0, 0] : [80, 700, 1500, 2700];
    const timers = steps.map((delay, i) =>
      setTimeout(() => {
        phase = i + 1;
        if (i === 0) {
          actors.target = data.dataset.actor_count;
          techniques.target = data.dataset.technique_count;
          edges.target = data.dataset.edge_count;
        }
      }, delay)
    );
    const onKey = (event) => {
      if (event.key === 'Escape' || event.key === 'Enter') onchoose('observe');
    };
    window.addEventListener('keydown', onKey);
    return () => {
      timers.forEach(clearTimeout);
      window.removeEventListener('keydown', onKey);
    };
  });
</script>

<section class="arrival" out:fade={{ duration: instant ? 0 : 420 }} aria-labelledby="arrival-title">
  <div class="veil"></div>
  <div class="frame">
    <p class="eyebrow" class:on={phase >= 1}>
      MITRE ATT&CK Enterprise · v{data.dataset.attack_version ?? '?'}
    </p>
    <h1 id="arrival-title" class:on={phase >= 1}>
      <span class="line">TTP Benzerlik</span>
      <span class="line accent">İstasyonu</span>
    </h1>

    <dl class="counts" class:on={phase >= 2}>
      <div><dt>aktör</dt><dd class="mono">{int(actors.current)}</dd></div>
      <div><dt>teknik</dt><dd class="mono">{int(techniques.current)}</dd></div>
      <div><dt>raporlanmış gözlem</dt><dd class="mono">{int(edges.current)}</dd></div>
    </dl>

    <ol class="principles">
      {#each principles as [title, body], i}
        <li class:on={phase >= 3} style:--i={i}>
          <span class="n mono">0{i + 1}</span>
          <div>
            <strong>{title}</strong>
            <p>{body}</p>
          </div>
        </li>
      {/each}
    </ol>

    <div class="cta" class:on={phase >= 4}>
      <button class="btn btn--signal big" onclick={() => onchoose('observe')}>
        Gözleme başla <span class="kbd">Enter</span>
      </button>
      <button class="btn big" onclick={() => onchoose('blind')}>Kör testle başla</button>
      <button class="btn btn--ghost big" onclick={() => onchoose('explore')}>Haritayı gez</button>
    </div>
  </div>

  <button class="skip mono" onclick={() => onchoose('observe')}>ATLA <span class="kbd">Esc</span></button>
</section>

<style>
  .arrival {
    position: fixed;
    inset: 0;
    z-index: 50;
    display: flex;
    align-items: safe center;
    overflow-y: auto;
    padding: clamp(40px, 7vh, 72px) clamp(24px, 7vw, 120px) clamp(24px, 4.5vh, 48px);
  }

  .veil {
    position: absolute;
    inset: 0;
    background: linear-gradient(90deg, rgba(4, 6, 10, 0.97) 0%, rgba(4, 6, 10, 0.88) 38%, rgba(4, 6, 10, 0.25) 70%, rgba(4, 6, 10, 0) 100%);
    pointer-events: none;
  }

  .frame {
    position: relative;
    max-width: 720px;
  }

  .eyebrow,
  h1 .line,
  .counts,
  .principles li,
  .cta {
    opacity: 0;
    translate: 0 14px;
    transition:
      opacity var(--t-slow) var(--ease-out),
      translate var(--t-slow) var(--ease-out);
  }

  .eyebrow.on,
  h1.on .line,
  .counts.on,
  .principles li.on,
  .cta.on {
    opacity: 1;
    translate: 0 0;
  }

  h1 {
    margin: clamp(6px, 1.4vh, 14px) 0 clamp(14px, 3vh, 28px);
    font-weight: 300;
    font-size: clamp(38px, min(6.4vw, 9.6vh), 84px);
    line-height: 0.98;
    letter-spacing: -0.025em;
  }

  h1 .line {
    display: block;
  }

  h1.on .line:nth-child(2) {
    transition-delay: 120ms;
  }

  .accent {
    color: var(--signal);
    font-weight: 400;
  }

  .counts {
    display: flex;
    gap: 36px;
    margin: 0 0 clamp(16px, 3.6vh, 36px);
    padding: clamp(10px, 1.9vh, 16px) 0;
    border-top: 1px solid var(--seam-2);
    border-bottom: 1px solid var(--seam-2);
  }

  .counts div {
    display: flex;
    flex-direction: column-reverse;
  }

  .counts dt {
    font-size: 12px;
    color: var(--ink-3);
    letter-spacing: 0.06em;
  }

  .counts dd {
    margin: 0;
    font-size: clamp(22px, 3.8vh, 30px);
    font-weight: 400;
    color: var(--ink);
  }

  .principles {
    list-style: none;
    padding: 0;
    margin: 0 0 clamp(18px, 3.6vh, 36px);
    display: grid;
    gap: clamp(10px, 2.2vh, 18px);
  }

  .principles li {
    display: grid;
    grid-template-columns: 36px 1fr;
    transition-delay: calc(var(--i) * 260ms);
  }

  .principles .n {
    color: var(--signal);
    font-size: 13px;
    padding-top: 3px;
  }

  .principles strong {
    font-weight: 500;
    font-size: clamp(16px, 2.5vh, 19px);
  }

  .principles p {
    margin: 4px 0 0;
    color: var(--ink-2);
    font-size: clamp(13px, 1.95vh, 14.5px);
    max-width: 62ch;
  }

  .cta {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
  }

  .big {
    height: clamp(40px, 6vh, 46px);
    padding: 0 20px;
    font-size: 14.5px;
  }

  .btn--signal .kbd {
    border-color: rgba(4, 6, 10, 0.35);
    color: rgba(4, 6, 10, 0.7);
  }

  .skip {
    position: absolute;
    top: 22px;
    right: 26px;
    display: flex;
    gap: 8px;
    align-items: center;
    font-size: 12px;
    letter-spacing: 0.14em;
    color: var(--ink-3);
  }

  .skip:hover {
    color: var(--ink);
  }

  @media (max-width: 860px) {
    .arrival {
      align-items: flex-start;
      padding-top: 72px;
      padding-bottom: 32px;
      overflow-y: auto;
    }
    .veil {
      position: fixed;
      background: rgba(4, 6, 10, 0.9);
    }
    .counts {
      gap: 20px;
    }
    .counts dd {
      font-size: 22px;
    }
  }
</style>
