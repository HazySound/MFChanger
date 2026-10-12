<script lang="ts">
  import { FolderOpen, RotateCcw, UserRound } from '@lucide/svelte'
  import { onMount, untrack } from 'svelte'
  import { app, markChanged } from '../lib/app.svelte'
  import { errorMessage, py } from '../lib/bridge'
  import EmptyState from '../lib/components/EmptyState.svelte'
  import ReplaceStage from '../lib/components/ReplaceStage.svelte'
  import SearchPanel from '../lib/components/SearchPanel.svelte'
  import Segmented from '../lib/components/Segmented.svelte'
  import SelectionHeader from '../lib/components/SelectionHeader.svelte'
  import ThumbRow from '../lib/components/ThumbRow.svelte'
  import { confirm, toast, toastError } from '../lib/notify.svelte'
  import type { ImageInfo, Manager, ManagerInfo } from '../lib/types'

  let { active }: { active: boolean } = $props()

  const MAX_RESULTS = 100

  let managers = $state.raw<Manager[]>([])
  let loadError = $state('')
  let loaded = $state(false)
  let query = $state('')
  let searchedQuery = $state('')
  let thumbs = $state<Record<string, string | null>>({})
  let thumbRequest = 0

  let selected = $state<Manager | null>(null)
  let info = $state<ManagerInfo | null>(null)
  let view = $state<'current' | 'official'>('current')
  let image = $state<ImageInfo | null>(null)
  let flipKey = $state(0)
  let busy = $state(false)

  const results = $derived.by(() => {
    const q = searchedQuery.trim().toLowerCase()
    if (!q) return []
    return managers.filter((m) => m.name.toLowerCase().includes(q) || m.team.toLowerCase().includes(q))
  })
  const shown = $derived(results.slice(0, MAX_RESULTS))

  const status = $derived.by(() => {
    if (loadError) return `감독 DB를 불러오지 못했습니다: ${loadError}`
    if (!loaded) return '감독 DB를 불러오는 중...'
    if (!searchedQuery.trim()) return `감독 이름 또는 팀명을 입력하세요. (총 ${managers.length}명)`
    if (!results.length) return '검색 결과가 없습니다.'
    return results.length > MAX_RESULTS ? `${results.length}명 중 ${MAX_RESULTS}명 표시` : `${results.length}명 검색됨`
  })

  async function loadManagers() {
    try {
      managers = (await (await py()).manager.entries()).sort((a, b) => a.name.localeCompare(b.name, 'ko'))
      loaded = true
    } catch (error) {
      loadError = errorMessage(error)
    }
  }

  async function loadInfo(manager: Manager) {
    try {
      const result = await (await py()).manager.info(manager.id)
      if (selected?.id === manager.id) info = result
    } catch (error) {
      toastError(error)
    }
  }

  onMount(loadManagers)

  // 보이는 목록의 썸네일 — 검색할 때와 게임 파일이 바뀔 때마다
  $effect(() => {
    void app.revision
    const ids = shown.map((m) => m.id)
    if (!ids.length) return
    const id = ++thumbRequest
    void py()
      .then((api) => api.manager.thumbnails(ids))
      .then((t) => {
        if (id === thumbRequest) thumbs = t
      })
      .catch(() => {}) // 썸네일은 보조 정보 — 실패해도 목록은 그대로 쓸 수 있다
  })

  // 데이터 동기화·이력 복원 등으로 바뀌면 감독 DB와 미리보기 다시 읽기
  $effect(() => {
    if (app.revision === 0) return
    untrack(() => {
      void loadManagers()
      if (selected) void loadInfo(selected)
    })
  })

  function select(manager: Manager) {
    selected = manager
    info = null
    void loadInfo(manager)
  }

  async function run(work: () => Promise<ManagerInfo>, message: string) {
    busy = true
    try {
      info = await work()
      view = 'current'
      flipKey += 1
      toast(message)
      markChanged()
    } catch (error) {
      toastError(error)
    } finally {
      busy = false
    }
  }

  function apply() {
    const m = selected
    const path = image?.path
    if (!m || !path) return
    void run(async () => (await py()).manager.replace(m.id, m.name, m.team, path), '감독 얼굴을 교체했습니다.')
  }

  async function restoreOfficial() {
    const m = selected
    if (!m) return
    const ok = await confirm(
      '공식 얼굴로 복원',
      `'${m.name}'의 얼굴을 공식 이미지로 되돌릴까요?\n넥슨 서버에서 공식 이미지를 받아 덮어씁니다.`,
      { confirmLabel: '복원' },
    )
    if (ok)
      void run(async () => (await py()).manager.restore_official(m.id, m.name, m.team), '공식 얼굴로 복원했습니다.')
  }
</script>

<div class="split-page">
  <SearchPanel
    bind:query
    placeholder="감독 이름 또는 팀명"
    disabled={!loaded}
    loading={!loaded && !loadError}
    {status}
    onSearch={() => (searchedQuery = query)}
  >
    {#each shown as manager (manager.id)}
      <ThumbRow thumb={thumbs[manager.id]} selected={selected?.id === manager.id} onclick={() => select(manager)}>
        <span class="title">{manager.name}</span>
        <span class="faint">{manager.team}</span>
      </ThumbRow>
    {/each}
  </SearchPanel>

  <div class="workspace">
    {#if selected}
      <SelectionHeader title={selected.name} changedAt={info?.changedAt ?? null}>
        {#snippet facts()}
          <span class="muted">{selected?.team}</span>
          <span class="faint file">{info?.fileName ?? ''}</span>
        {/snippet}
        {#snippet actions()}
          <button
            type="button"
            class="btn"
            disabled={!info}
            onclick={async () => info && (await py()).app.reveal(info.path)}
          >
            <FolderOpen size={15} /> 파일 위치 열기
          </button>
          <button type="button" class="btn" disabled={busy} onclick={restoreOfficial}>
            <RotateCcw size={15} /> 공식 얼굴로 복원
          </button>
        {/snippet}
      </SelectionHeader>

      <ReplaceStage
        currentSrc={view === 'current' ? (info?.currentUrl ?? null) : (info?.officialUrl ?? null)}
        currentLabel={view === 'current' ? '현재 얼굴' : '공식 얼굴'}
        currentPlaceholder={view === 'official' ? '공식 얼굴 이미지가 없는 감독입니다' : '이미지 없음'}
        {flipKey}
        {image}
        onImage={(i) => (image = i)}
        pasteEnabled={active}
        applyLabel="감독 얼굴 교체"
        applying={busy}
        canApply={!!image}
        onApply={apply}
      >
        {#snippet currentTools()}
          <Segmented
            label="미리보기"
            options={[
              { value: 'current', label: '현재' },
              { value: 'official', label: '공식' },
            ]}
            value={view}
            onChange={(v) => (view = v)}
          />
        {/snippet}
        {#snippet currentCaption()}
          {#if info?.usesGeneric}
            <p class="faint">전용 이미지가 없어 공용 얼굴(generic.png)을 씁니다. 교체하면 공용 얼굴이 바뀝니다.</p>
          {/if}
        {/snippet}
      </ReplaceStage>
    {:else}
      <EmptyState icon={UserRound} title="감독을 선택하세요">
        <p class="muted">왼쪽에서 감독 이름이나 팀명으로 검색하세요.</p>
      </EmptyState>
    {/if}
  </div>
</div>

<style>
  .file {
    user-select: text;
  }
</style>
