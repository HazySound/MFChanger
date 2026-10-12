<script lang="ts">
  import { FolderOpen, RotateCcw } from '@lucide/svelte'
  import { untrack } from 'svelte'
  import { app } from '../../lib/app.svelte'
  import { errorMessage, py } from '../../lib/bridge'
  import ReplaceStage from '../../lib/components/ReplaceStage.svelte'
  import Segmented from '../../lib/components/Segmented.svelte'
  import type { FaceTarget, ImageInfo, Player, ReplaceResult } from '../../lib/types'
  import { confirmReplace, replaceFace, restoreOfficialFace, type Phase } from './faceActions'
  import CardHeader from './CardHeader.svelte'

  interface Props {
    card: Player
    image: ImageInfo | null
    onImage: (image: ImageInfo) => void
    pasteEnabled: boolean
  }

  let { card, image, onImage, pasteEnabled }: Props = $props()

  type View = 'current' | 'official'
  let view = $state<View>('current')
  let target = $state<FaceTarget | null>(null)
  let loadError = $state('')
  let flipKey = $state(0)
  let phase = $state<Phase>('idle')
  let request = 0
  let seenRevision = untrack(() => app.revision)

  const preview = $derived(view === 'current' ? (target?.currentUrl ?? null) : (target?.officialUrl ?? null))

  /** keep: 다시 확인하는 동안 지금 정보를 그대로 보여줄지 (게임 파일만 바뀐 경우) */
  async function load(spid: number, name: string, keep: boolean) {
    const id = ++request
    if (!keep) target = null
    loadError = ''
    try {
      const result = await (await py()).face.resolve(spid, name)
      if (id === request) target = result
    } catch (error) {
      if (id === request) loadError = errorMessage(error)
    }
  }

  // 카드를 고르면 새로 확인
  $effect(() => {
    const { id, name } = card
    untrack(() => load(id, name, false))
  })

  // 다른 탭·이력 등에서 게임 파일이 바뀌면 조용히 다시 확인
  $effect(() => {
    const revision = app.revision
    if (revision === seenRevision) return
    seenRevision = revision
    untrack(() => load(card.id, card.name, true))
  })

  function showResult(result: ReplaceResult) {
    if (target) target = { ...target, currentUrl: result.currentUrl, changedAt: result.changedAt }
    view = 'current'
    flipKey += 1
  }

  async function apply() {
    if (phase !== 'idle' || !target || !image) return
    phase = 'confirm'
    try {
      const sharing = [card.id, ...target.sharedSpids]
      if (!(await confirmReplace(card.name, target.relative, sharing, target.verified))) return
      phase = 'apply'
      const result = await replaceFace(card.id, card.name, image, target.relative)
      if (result) showResult(result)
    } finally {
      phase = 'idle'
    }
  }

  async function restoreOfficial() {
    if (phase !== 'idle' || !target) return
    phase = 'restore'
    try {
      const result = await restoreOfficialFace(card.id, card.name, target.relative)
      if (result) showResult(result)
    } finally {
      phase = 'idle'
    }
  }
</script>

<div class="card-mode">
  <CardHeader {card} changedAt={target?.changedAt ?? null}>
    {#snippet actions()}
      <button
        type="button"
        class="btn"
        disabled={!target}
        onclick={async () => target && (await py()).app.reveal_game_file(target.relative)}
      >
        <FolderOpen size={15} /> 파일 위치 열기
      </button>
      <button type="button" class="btn" disabled={!target || phase !== 'idle'} onclick={restoreOfficial}>
        <RotateCcw size={15} /> 공식 미페로 복원
      </button>
    {/snippet}
  </CardHeader>

  <ReplaceStage
    currentSrc={target ? preview : null}
    currentLabel={view === 'current' ? '현재 미페' : '공식 미페'}
    currentPlaceholder={target
      ? '게임 폴더에 파일이 없습니다'
      : loadError
        ? '게임 파일을 확인하지 못했습니다'
        : '게임 파일 확인 중'}
    {flipKey}
    {image}
    {onImage}
    {pasteEnabled}
    applyLabel="미페 교체"
    applying={phase === 'apply'}
    canApply={!!target && !!image && phase === 'idle'}
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
      {#if target}
        <p class="faint path" title={target.relative}>{target.relative}</p>
        {#if !target.verified}
          <p class="warn-text">데이터센터 확인 실패: 추정 경로입니다</p>
        {:else if target.sharedSpids.length}
          <p class="warn-text">이 선수의 카드 {target.sharedSpids.length + 1}장이 같은 파일을 씁니다</p>
        {/if}
      {:else if loadError}
        <p class="warn-text">{loadError}</p>
        <button type="button" class="btn small" onclick={() => load(card.id, card.name, false)}>다시 시도</button>
      {/if}
    {/snippet}
  </ReplaceStage>
</div>

<style>
  .card-mode {
    display: grid;
    align-content: start;
    gap: 14px;
  }

  .path {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    user-select: text;
  }
</style>
