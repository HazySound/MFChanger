<script lang="ts">
  import { ChevronRight } from '@lucide/svelte'
  import { slide } from 'svelte/transition'
  import { app } from '../../lib/app.svelte'
  import { py } from '../../lib/bridge'
  import SeasonBadge from '../../lib/components/SeasonBadge.svelte'
  import ThumbRow from '../../lib/components/ThumbRow.svelte'
  import type { PlayerGroup } from '../../lib/meta.svelte'
  import type { Player } from '../../lib/types'

  interface Props {
    group: PlayerGroup
    expanded: boolean
    selectedSpid: number | null
    onToggle: () => void
    onSelect: (card: Player) => void
  }

  let { group, expanded, selectedSpid, onToggle, onSelect }: Props = $props()

  let thumbs = $state<Record<string, string | null>>({})

  // 펼쳐져 있는 동안: 처음 펼칠 때와 게임 파일이 바뀔 때마다 썸네일을 다시 받는다
  $effect(() => {
    if (!expanded) return
    void app.revision
    const { pid, name, cards } = group
    void py()
      .then((api) =>
        api.face.thumbnails(
          pid,
          name,
          cards.map((c) => c.id),
        ),
      )
      .then((result) => (thumbs = result))
      .catch(() => {}) // 썸네일은 보조 정보 — 실패해도 목록은 그대로 쓸 수 있다
  })
</script>

<div class="group">
  <button type="button" class="head" class:open={expanded} aria-expanded={expanded} onclick={onToggle}>
    <span class="chevron"><ChevronRight size={15} /></span>
    <span class="name">{group.name}</span>
    <span class="faint">{group.cards.length}장</span>
  </button>

  {#if expanded}
    <div class="cards" transition:slide={{ duration: 180 }}>
      {#each group.cards as card (card.id)}
        <ThumbRow
          thumb={thumbs[card.id]}
          selected={card.id === selectedSpid}
          data-spid={card.id}
          onclick={() => onSelect(card)}
        >
          <span class="title">{card.name}</span>
          <SeasonBadge spid={card.id} />
        </ThumbRow>
      {/each}
    </div>
  {/if}
</div>

<style>
  .head {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    height: 40px;
    padding: 0 10px;
    border: 0;
    border-radius: var(--radius-control);
    background: none;
    text-align: left;
    cursor: pointer;
    transition: background 0.15s;
  }

  .head:hover,
  .head.open {
    background: var(--surface-2);
  }

  .chevron {
    display: inline-flex;
    color: var(--text-3);
    transition: transform 0.18s var(--ease-out);
  }

  .head.open .chevron {
    transform: rotate(90deg);
  }

  .name {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-weight: 700;
  }

  .cards {
    display: grid;
    gap: 2px;
    margin: 2px 0 6px;
    padding-left: 14px;
  }
</style>
