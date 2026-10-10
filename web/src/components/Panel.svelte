<script>
  let { index = '', kicker = '', title = '', subtitle = '', actions, children, class: className = '' } = $props();
</script>

<section class="panel {className}">
  {#if kicker || title}
    <header>
      <div class="kicker mono">
        {#if index}<span class="index">{index}</span>{/if}
        <span>{kicker}</span>
        {#if actions}<div class="actions">{@render actions()}</div>{/if}
      </div>
      {#if title}<h2>{title}</h2>{/if}
      {#if subtitle}<p class="subtitle">{subtitle}</p>{/if}
    </header>
  {/if}
  <div class="body scroll">
    {@render children?.()}
  </div>
</section>

<style>
  .panel {
    position: relative;
    display: flex;
    flex-direction: column;
    min-height: 0;
    background: linear-gradient(180deg, rgba(15, 22, 34, 0.96), rgba(10, 15, 23, 0.96));
    border: 1px solid var(--seam);
    box-shadow: 0 24px 60px -30px rgba(0, 0, 0, 0.8);
  }

  .panel::before,
  .panel::after {
    content: '';
    position: absolute;
    width: 10px;
    height: 10px;
    border-color: var(--seam-3);
    border-style: solid;
    pointer-events: none;
  }

  .panel::before {
    top: -1px;
    left: -1px;
    border-width: 1px 0 0 1px;
  }

  .panel::after {
    bottom: -1px;
    right: -1px;
    border-width: 0 1px 1px 0;
  }

  header {
    padding: 18px 20px 14px;
    border-bottom: 1px solid var(--seam);
  }

  .kicker {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 11.5px;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: var(--ink-3);
  }

  .index {
    color: var(--signal);
  }

  .actions {
    margin-left: auto;
    display: flex;
    gap: 6px;
    letter-spacing: normal;
    text-transform: none;
  }

  h2 {
    margin: 8px 0 0;
    font-size: 22px;
    font-weight: 400;
    letter-spacing: -0.01em;
    line-height: 1.2;
  }

  .subtitle {
    margin: 6px 0 0;
    font-size: 13.5px;
    color: var(--ink-2);
  }

  .body {
    flex: 1;
    min-height: 0;
    padding: 16px 20px 20px;
    container: panel / inline-size;
  }

  @media (max-height: 820px) {
    header {
      padding: 12px 18px 10px;
    }

    h2 {
      margin-top: 4px;
      font-size: 19px;
    }

    .subtitle {
      font-size: 12.5px;
      margin-top: 3px;
    }

    .body {
      padding: 12px 18px 16px;
    }
  }
</style>
