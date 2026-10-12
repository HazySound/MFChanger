<script lang="ts">
  import type { Component, Snippet } from 'svelte'

  interface Props {
    icon: Component
    title: string
    children?: Snippet
  }

  let { icon: Icon, title, children }: Props = $props()
</script>

<div class="empty">
  <Icon size={40} strokeWidth={1.4} />
  <h2>{title}</h2>
  {@render children?.()}
</div>

<style>
  .empty {
    display: grid;
    justify-items: center;
    gap: 10px;
    padding: 56px 24px;
    color: var(--text-3);
    text-align: center;
  }

  h2 {
    color: var(--text);
  }
</style>
