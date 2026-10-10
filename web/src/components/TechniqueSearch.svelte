<script>
  import { station } from '../lib/station.svelte.js';
  import { searchTechniques } from '../lib/search.js';
  import { looksLikeList } from '../lib/parse.js';
  import { heatColor } from '../lib/format.js';

  let { input = $bindable() } = $props();

  let text = $state('');
  let cursor = $state(0);
  let open = $state(false);

  const list = $derived(station.data?.techniques ?? []);
  const tacticNames = $derived(new Map((station.data?.tactics ?? []).map((t) => [t.id, t.name])));
  const results = $derived(searchTechniques(list, text, 7));
  const chosen = $derived(new Set(station.query));

  $effect(() => {
    results;
    cursor = 0;
  });

  function add(technique) {
    station.add([technique.id]);
    text = '';
    open = false;
    input?.focus();
  }

  function addAll(blob) {
    const { added, unknown } = station.addText(blob);
    text = '';
    open = false;
    const parts = [];
    if (added) parts.push(`${added} teknik eklendi`);
    if (unknown.length) parts.push(`${unknown.length} girdi tanınmadı`);
    if (parts.length) station.notify(parts.join(' · '));
  }

  function onkeydown(event) {
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      open = true;
      cursor = Math.min(results.length - 1, cursor + 1);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      cursor = Math.max(0, cursor - 1);
    } else if (event.key === 'Enter') {
      event.preventDefault();
      if (looksLikeList(text)) addAll(text);
      else if (results[cursor]) add(results[cursor]);
    } else if (event.key === 'Escape') {
      text = '';
      open = false;
      input?.blur();
    }
  }

  function onpaste(event) {
    const blob = event.clipboardData?.getData('text') ?? '';
    if (looksLikeList(blob)) {
      event.preventDefault();
      addAll(blob);
    }
  }
</script>

<div class="search" class:open={open && results.length}>
  <label class="sr-only" for="technique-search">Teknik ara veya liste yapıştır</label>
  <div class="field">
    <svg viewBox="0 0 20 20" width="16" height="16" aria-hidden="true">
      <circle cx="8.5" cy="8.5" r="5.5" fill="none" stroke="currentColor" stroke-width="1.4" />
      <path d="M13 13l4 4" stroke="currentColor" stroke-width="1.4" />
    </svg>
    <input
      id="technique-search"
      bind:this={input}
      bind:value={text}
      autocomplete="off"
      spellcheck="false"
      placeholder="T1566, phishing, credential…"
      role="combobox"
      aria-expanded={open && results.length > 0}
      aria-controls="technique-results"
      aria-activedescendant={open && results[cursor] ? `opt-${results[cursor].id}` : undefined}
      oninput={() => (open = true)}
      onfocus={() => (open = true)}
      onblur={() => setTimeout(() => (open = false), 120)}
      {onkeydown}
      {onpaste}
    />
    <span class="kbd">/</span>
  </div>

  {#if open && results.length}
    <ul id="technique-results" role="listbox" class="results">
      {#each results as technique, i (technique.id)}
        <li
          id="opt-{technique.id}"
          role="option"
          aria-selected={i === cursor}
          class:active={i === cursor}
          class:chosen={chosen.has(technique.id)}
          onpointerenter={() => (cursor = i)}
          onpointerdown={(event) => {
            event.preventDefault();
            add(technique);
          }}
        >
          <span class="id mono" style:color={heatColor(technique.heat)}>{technique.id}</span>
          <span class="name">
            {technique.name}
            <small>{technique.tactics.map((t) => tacticNames.get(t) ?? t).join(' · ')}</small>
          </span>
          <span class="rarity">
            <span class="track"><i style:width="{Math.max(6, technique.heat * 100)}%" style:background={heatColor(technique.heat)}></i></span>
            <small class="mono">{technique.actor_count} aktör</small>
          </span>
        </li>
      {/each}
    </ul>
  {/if}
  <p class="hint">Birden çok kimliği yapıştırırsan hepsi tek seferde eklenir.</p>
</div>

<style>
  .search {
    position: relative;
  }

  .field {
    display: flex;
    align-items: center;
    gap: 10px;
    height: 46px;
    padding: 0 12px;
    background: var(--void);
    border: 1px solid var(--seam-2);
    color: var(--ink-3);
    transition: border-color var(--t-fast);
  }

  .field:focus-within {
    border-color: var(--signal);
    color: var(--signal);
  }

  input {
    flex: 1;
    min-width: 0;
    height: 100%;
    background: none;
    border: 0;
    outline: none;
    font-family: var(--mono);
    font-size: 14px;
    color: var(--ink);
  }

  input::placeholder {
    color: var(--ink-3);
  }

  .results {
    position: absolute;
    z-index: 30;
    left: 0;
    right: 0;
    top: 47px;
    margin: 0;
    padding: 4px 0;
    list-style: none;
    background: var(--hull-2);
    border: 1px solid var(--seam-2);
    box-shadow: 0 18px 40px -12px rgba(0, 0, 0, 0.85);
    animation: drop var(--t-base) var(--ease-out) both;
  }

  li {
    display: grid;
    grid-template-columns: 56px 1fr 92px;
    gap: 10px;
    align-items: center;
    padding: 8px 12px;
    cursor: pointer;
    border-left: 2px solid transparent;
  }

  li.active {
    background: var(--hull-3);
    border-left-color: var(--signal);
  }

  li.chosen .name::after {
    content: ' ✓';
    color: var(--lock);
  }

  .id {
    font-size: 13px;
  }

  .name {
    font-size: 13.5px;
    color: var(--ink);
    line-height: 1.3;
    min-width: 0;
  }

  .name small {
    display: block;
    font-size: 12px;
    color: var(--ink-3);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .rarity {
    display: flex;
    flex-direction: column;
    gap: 4px;
    align-items: flex-end;
  }

  .rarity small {
    font-size: 11.5px;
    color: var(--ink-3);
  }

  .track {
    width: 100%;
    height: 3px;
    background: var(--seam);
  }

  .track i {
    display: block;
    height: 100%;
  }

  .hint {
    margin: 8px 0 0;
    font-size: 12px;
    color: var(--ink-3);
  }

  @keyframes drop {
    from {
      opacity: 0;
      translate: 0 -6px;
    }
  }
</style>
