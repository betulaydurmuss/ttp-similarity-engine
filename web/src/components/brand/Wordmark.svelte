<script>
  import { WORD_LETTERS, WORD_WIDTH } from '../../lib/brand.js';

  let { height = 16, class: className = '' } = $props();
</script>

<svg
  class="wordmark {className}"
  viewBox="0 0 {WORD_WIDTH} 100"
  height={height}
  width={(height * WORD_WIDTH) / 100}
  role="img"
  aria-label="YILDIZ"
  fill="currentColor"
  fill-rule="evenodd"
>
  {#each WORD_LETTERS as letter, i}
    <path d={letter.d} style:--i={i} />
  {/each}
</svg>

<style>
  .wordmark {
    display: block;
    flex-shrink: 0;
  }
</style>
