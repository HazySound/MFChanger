<script lang="ts">
  import { ArrowRight } from '@lucide/svelte'

  interface Props {
    before: string | null
    after: string | null
    dimmed?: boolean
  }

  let { before, after, dimmed = false }: Props = $props()
</script>

<div class="before-after" class:dimmed>
  {#each [before, after] as src, i (i)}
    {#if i === 1}<ArrowRight size={14} />{/if}
    <span class="thumb">
      {#if src}<img {src} alt={i === 0 ? '교체 전' : '교체 후'} loading="lazy" />{:else}<span>-</span>{/if}
    </span>
  {/each}
</div>

<style>
  .before-after {
    display: flex;
    align-items: center;
    gap: 6px;
    color: var(--text-3);
  }

  .dimmed {
    opacity: 0.5;
    filter: saturate(0.4);
  }

  .thumb {
    display: grid;
    place-items: center;
    width: 52px;
    height: 52px;
    border-radius: 6px;
    background: var(--surface-2);
    overflow: hidden;
    font-size: var(--text-xs);
  }

  img {
    width: 100%;
    height: 100%;
    object-fit: contain;
  }
</style>
