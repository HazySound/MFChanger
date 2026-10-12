<script lang="ts">
  import { FolderOpen, History, RefreshCw } from '@lucide/svelte'
  import { app, markChanged } from '../../lib/app.svelte'
  import { py } from '../../lib/bridge'
  import EmptyState from '../../lib/components/EmptyState.svelte'
  import { confirm, toast, toastError } from '../../lib/notify.svelte'
  import type { HistoryData } from '../../lib/types'
  import BeforeAfter from './BeforeAfter.svelte'
  import FaceHistoryGroup from './FaceHistoryGroup.svelte'

  let { active }: { active: boolean } = $props()

  let data = $state<HistoryData | null>(null)

  const isEmpty = $derived(!!data && !data.faces.length && !data.crests.length && !data.managers.length)

  async function load() {
    try {
      data = await (await py()).history.entries()
    } catch (error) {
      toastError(error)
    }
  }

  // 탭을 열 때마다, 그리고 열려 있는 동안 다른 곳에서 바뀌면 다시 읽기
  $effect(() => {
    void app.revision
    if (active) void load()
  })

  async function act(
    question: { title: string; message: string; label: string; danger?: boolean },
    work: () => Promise<void>,
    message: string,
  ) {
    const ok = await confirm(question.title, question.message, {
      confirmLabel: question.label,
      danger: question.danger,
    })
    if (!ok) return
    try {
      await work()
      toast(message)
      markChanged()
    } catch (error) {
      toastError(error)
    }
  }
</script>

<div class="history-page">
  <div class="top">
    <h1>변경 이력</h1>
    <button type="button" class="btn ghost" onclick={load}><RefreshCw size={15} /> 새로고침</button>
  </div>

  {#if isEmpty}
    <EmptyState icon={History} title="아직 변경한 기록이 없습니다">
      <p class="muted">미페·크레스트·감독 얼굴을 교체하면 여기에서 되돌릴 수 있습니다.</p>
    </EmptyState>
  {:else if data}
    <section>
      <h2>미페</h2>
      {#each data.faces as group (group.spid)}
        <FaceHistoryGroup {group} />
      {:else}
        <p class="faint">미페 변경 기록이 없습니다.</p>
      {/each}
    </section>

    <section>
      <h2>크레스트</h2>
      {#each data.crests as row (row.crestId)}
        <div class="row panel">
          <span class="id">c{row.crestId}</span>
          <BeforeAfter before={row.beforeUrl} after={row.afterUrl} />
          <div class="meta">
            <span class="source" title={row.source}>{row.source}</span>
            <span class="faint">{row.changedAt}</span>
          </div>
          <button
            type="button"
            class="btn small {row.hasBackup ? '' : 'danger'}"
            onclick={() =>
              act(
                row.hasBackup
                  ? {
                      title: '크레스트 복원',
                      message: `크레스트 ${row.crestId}번을 원래대로 되돌릴까요?`,
                      label: '복원',
                    }
                  : {
                      title: '교체한 파일 삭제',
                      message: `크레스트 ${row.crestId}번의 교체 파일을 삭제할까요?\n백업이 없어 파일만 지우며, 게임을 다시 실행하면 원본을 다시 받습니다.`,
                      label: '삭제',
                      danger: true,
                    },
                async () => (await py()).history.restore_crest(row.crestId),
                row.hasBackup ? '크레스트를 복원했습니다.' : '교체한 파일을 삭제했습니다.',
              )}
          >
            {row.hasBackup ? '복원' : '삭제'}
          </button>
          <button type="button" class="btn small" onclick={async () => (await py()).app.reveal(row.backupDir)}>
            <FolderOpen size={14} /> 백업 폴더
          </button>
        </div>
      {:else}
        <p class="faint">크레스트 변경 기록이 없습니다.</p>
      {/each}
    </section>

    <section>
      <h2>감독</h2>
      {#each data.managers as row (row.managerId)}
        <div class="row panel">
          <span class="thumb">
            {#if row.currentUrl}
              <img src={row.currentUrl} alt="" loading="lazy" />
            {/if}
          </span>
          <div class="meta">
            <span class="source">{row.name} <span class="faint">{row.team}</span></span>
            <span class="faint">{row.source}, {row.changedAt}</span>
          </div>
          <button
            type="button"
            class="btn small"
            onclick={() =>
              act(
                {
                  title: '공식 얼굴로 복원',
                  message: `'${row.name}'의 얼굴을 공식 이미지로 되돌릴까요?`,
                  label: '복원',
                },
                async () => (await py()).history.restore_manager(row.managerId),
                '공식 얼굴로 복원했습니다.',
              )}
          >
            공식 복원
          </button>
          <button
            type="button"
            class="btn small danger"
            onclick={() =>
              act(
                {
                  title: '기록 삭제',
                  message: `'${row.name}' 변경 기록을 삭제할까요?\n현재 게임 파일은 바뀌지 않습니다.`,
                  label: '삭제',
                  danger: true,
                },
                async () => (await py()).history.delete_manager_record(row.managerId),
                '기록을 삭제했습니다.',
              )}
          >
            삭제
          </button>
        </div>
      {:else}
        <p class="faint">감독 변경 기록이 없습니다.</p>
      {/each}
    </section>
  {/if}
</div>

<style>
  .history-page {
    display: grid;
    align-content: start;
    gap: 22px;
    width: 100%; /* 격자 안 margin: auto 는 내용 폭으로 줄어들므로 명시 */
    max-width: 980px;
    margin: 0 auto;
    padding: 16px 20px 28px;
    overflow-y: auto;
  }

  .top {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  h1 {
    font-size: var(--text-xl);
    font-weight: 800;
  }

  section {
    display: grid;
    gap: 8px;
  }

  h2 {
    font-size: var(--text-md);
    color: var(--text-2);
  }

  .row {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 8px 12px;
  }

  .id {
    width: 72px;
    font-weight: 700;
    user-select: text;
  }

  .thumb {
    width: 52px;
    height: 52px;
    border-radius: 6px;
    background: var(--surface-2);
    overflow: hidden;
  }

  .thumb img {
    width: 100%;
    height: 100%;
    object-fit: contain;
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
