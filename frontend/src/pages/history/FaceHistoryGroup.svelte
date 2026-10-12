<script lang="ts">
  import { ChevronRight, FolderOpen } from '@lucide/svelte'
  import { SvelteSet } from 'svelte/reactivity'
  import { slide } from 'svelte/transition'
  import { markChanged } from '../../lib/app.svelte'
  import { py } from '../../lib/bridge'
  import { confirm, toast, toastError } from '../../lib/notify.svelte'
  import type { FaceHistoryGroup } from '../../lib/types'
  import BeforeAfter from './BeforeAfter.svelte'

  let { group }: { group: FaceHistoryGroup } = $props()

  let open = $state(true)
  const checked = new SvelteSet<number>()

  async function act(work: () => Promise<unknown>, message: string) {
    try {
      await work()
      toast(message)
      checked.clear()
      markChanged() // 이력 탭 목록과 다른 탭의 "변경됨" 표시를 함께 갱신
    } catch (error) {
      toastError(error)
    }
  }

  async function restoreLatest(hasBackup: boolean) {
    const ok = await confirm(
      hasBackup ? '이전 미페로 복원' : '교체한 파일 삭제',
      hasBackup
        ? `'${group.playerName}'의 미페를 이 기록 이전 상태로 되돌릴까요?`
        : `'${group.playerName}'의 교체 파일을 삭제할까요?\n백업이 없어 파일만 지우며, 게임을 다시 실행하면 공식 미페를 다시 받습니다.`,
      { confirmLabel: hasBackup ? '복원' : '삭제', danger: !hasBackup },
    )
    if (ok)
      await act(
        async () => (await py()).history.restore_face(group.spid),
        hasBackup ? '복원했습니다.' : '교체한 파일을 삭제했습니다.',
      )
  }

  async function deleteRecords(positions: number[] | null) {
    const count = positions?.length ?? group.entries.length
    const ok = await confirm(
      positions ? '선택한 기록 삭제' : '전체 기록 삭제',
      `${positions ? '' : `'${group.playerName}'의 `}기록 ${count}개와 백업 파일을 삭제할까요?\n현재 게임 파일은 바뀌지 않습니다.`,
      { confirmLabel: '삭제', danger: true },
    )
    if (ok)
      await act(
        async () => (await py()).history.delete_face_records(group.spid, positions),
        `기록 ${count}개를 삭제했습니다.`,
      )
  }

  function toggleCheck(position: number) {
    if (checked.has(position)) checked.delete(position)
    else checked.add(position)
  }
</script>

<article class="group panel">
  <header>
    <button type="button" class="toggle" aria-expanded={open} onclick={() => (open = !open)}>
      <span class="chevron" class:open><ChevronRight size={15} /></span>
      <span class="name">{group.playerName}</span>
      <span class="faint">기록 {group.entries.length}개</span>
    </button>
    <div class="tools">
      <button
        type="button"
        class="btn danger small"
        disabled={!checked.size}
        onclick={() => deleteRecords([...checked])}
      >
        선택 삭제{checked.size ? ` (${checked.size})` : ''}
      </button>
      <button type="button" class="btn danger small" onclick={() => deleteRecords(null)}>전체 삭제</button>
      <button type="button" class="btn small" onclick={async () => (await py()).app.reveal(group.backupDir)}>
        <FolderOpen size={14} /> 백업 폴더
      </button>
    </div>
  </header>

  {#if open}
    <ol transition:slide={{ duration: 180 }}>
      {#each group.entries as entry, i (entry.position)}
        {@const latest = i === 0}
        <li class:latest>
          <input
            type="checkbox"
            aria-label="기록 선택"
            checked={checked.has(entry.position)}
            onchange={() => toggleCheck(entry.position)}
          />
          <BeforeAfter before={entry.beforeUrl} after={entry.afterUrl} dimmed={!latest} />
          <div class="meta">
            <span class="source" title={entry.source}>{entry.source}</span>
            <span class="faint">{entry.changedAt}</span>
          </div>
          {#if latest}
            <button
              type="button"
              class="btn small {entry.hasBackup ? '' : 'danger'}"
              onclick={() => restoreLatest(entry.hasBackup)}
            >
              {entry.hasBackup ? '복원' : '삭제 (백업 없음)'}
            </button>
          {/if}
        </li>
      {/each}
    </ol>
  {/if}
</article>

<style>
  .group {
    padding: 6px;
  }

  header {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
  }

  .toggle {
    display: flex;
    flex: 1;
    align-items: center;
    gap: 8px;
    min-width: 200px;
    height: 40px;
    padding: 0 8px;
    border: 0;
    border-radius: var(--radius-control);
    background: none;
    text-align: left;
    cursor: pointer;
  }

  .toggle:hover {
    background: var(--surface-2);
  }

  .chevron {
    display: inline-flex;
    color: var(--text-3);
    transition: transform 0.18s var(--ease-out);
  }

  .chevron.open {
    transform: rotate(90deg);
  }

  .name {
    font-weight: 700;
  }

  .tools {
    display: flex;
    gap: 6px;
    padding-right: 4px;
  }

  ol {
    display: grid;
    gap: 4px;
    margin: 4px 0 0;
    padding: 0;
    list-style: none;
  }

  li {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 8px 12px;
    border-radius: var(--radius-control);
  }

  li.latest {
    background: var(--surface-2);
  }

  input[type='checkbox'] {
    width: 16px;
    height: 16px;
    accent-color: var(--gold);
  }

  .meta {
    display: grid;
    flex: 1;
    min-width: 0;
  }

  .source {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: var(--text-sm);
  }
</style>
