<script>
  import { EMBLEM_BODY, EMBLEM_STAR, STAR_CENTER } from '../../lib/brand.js';

  let { size = 24, title = '', twinkle = false, class: className = '' } = $props();
</script>

<svg
  class="emblem {className}"
  class:twinkle
  viewBox="0 0 100 100"
  width={size}
  height={size}
  role={title ? 'img' : undefined}
  aria-label={title || undefined}
  aria-hidden={title ? undefined : 'true'}
>
  <path class="body" fill="currentColor" fill-rule="evenodd" d={EMBLEM_BODY} />
  <path class="star" d={EMBLEM_STAR} style:transform-origin="{STAR_CENTER[0]}px {STAR_CENTER[1]}px" />
</svg>

<style>
  .emblem {
    display: block;
    flex-shrink: 0;
    overflow: visible;
  }

  .star {
    fill: var(--signal);
    transform-box: view-box;
  }

  .twinkle:hover .star,
  :global(:hover > .twinkle) .star,
  :global(:focus-visible > .twinkle) .star {
    animation: twinkle 1100ms var(--ease-out);
  }

  @keyframes twinkle {
    35% {
      transform: rotate(72deg) scale(1.3);
      filter: drop-shadow(0 0 2px #ffb54a);
    }
    100% {
      transform: rotate(144deg) scale(1);
    }
  }
</style>
