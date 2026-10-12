<script lang="ts">
  import type { Snippet } from 'svelte'

  interface Props {
    thumb: string | null | undefined
    selected: boolean
    onclick: () => void
    /** 썸네일 오른쪽 글자 */
    children: Snippet
    [attr: `data-${string}`]: unknown
  }

  let { thumb, selected, onclick, children, ...data }: Props = $props()
</script>

<button type="button" class="row" class:selected {onclick} {...data}>
  <span class="thumb">
    {#if thumb}
      <img src={thumb} alt="" loading="lazy" />
    {/if}
  </span>
  <span class="text">{@render children()}</span>
</button>

<style>
  .row {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
    padding: 5px 8px;
    border: 1px solid transparent;
    border-radius: var(--radius-control);
    background: none;
    text-align: left;
    cursor: pointer;
    transition:
      background 0.15s,
      border-color 0.15s;
  }

  .row:hover {
    background: var(--surface-2);
  }

  .row.selected {
    background: var(--gold-soft);
    border-color: rgb(242 201 76 / 0.5);
  }

  .thumb {
    flex: none;
    width: 44px;
    height: 44px;
    border-radius: 6px;
    background: var(--surface-2);
    overflow: hidden;
  }

  .thumb img {
    width: 100%;
    height: 100%;
    object-fit: contain;
  }

  .text {
    display: grid;
    gap: 2px;
    min-width: 0;
  }

  .text :global(.title) {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: var(--text-sm);
    font-weight: 600;
  }
</style>
