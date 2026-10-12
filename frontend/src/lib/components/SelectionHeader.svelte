<script lang="ts">
  import type { Snippet } from 'svelte'

  interface Props {
    title: string
    changedAt: string | null
    /** 제목 아래 정보 (시즌, 팀, 파일명 등) */
    facts?: Snippet
    /** 오른쪽 동작 버튼 */
    actions?: Snippet
  }

  let { title, changedAt, facts, actions }: Props = $props()
</script>

<div class="selection">
  <div class="who">
    <h2>{title}</h2>
    <div class="facts">
      {@render facts?.()}
      {#if changedAt}<span class="changed-text">변경됨 {changedAt}</span>{/if}
    </div>
  </div>
  <div class="actions">{@render actions?.()}</div>
</div>

<style>
  .selection {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 12px 16px;
  }

  .who {
    display: grid;
    gap: 4px;
    min-width: 0;
  }

  h2 {
    font-size: var(--text-xl);
    font-weight: 800;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .facts {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px 14px;
    min-height: 20px;
  }

  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
</style>
