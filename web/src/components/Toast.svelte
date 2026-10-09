<script>
  import { fly } from 'svelte/transition';
  import { prefersReducedMotion } from 'svelte/motion';
  import { station } from '../lib/station.svelte.js';
</script>

<div class="toaster" aria-live="polite">
  {#if station.toast}
    {#key station.toast.stamp}
      <div class="toast" transition:fly={{ y: 12, duration: prefersReducedMotion.current ? 0 : 260 }}>
        {station.toast.message}
      </div>
    {/key}
  {/if}
</div>

<style>
  .toaster {
    position: fixed;
    left: 50%;
    bottom: 24px;
    transform: translateX(-50%);
    z-index: 60;
    pointer-events: none;
  }

  .toast {
    padding: 10px 16px;
    background: var(--hull-3);
    border: 1px solid var(--seam-3);
    border-left: 2px solid var(--signal);
    font-size: 13.5px;
    color: var(--ink);
    box-shadow: 0 16px 40px -12px rgba(0, 0, 0, 0.8);
  }
</style>
