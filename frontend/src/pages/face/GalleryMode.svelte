<script lang="ts">
  import { FolderOpen, LoaderCircle, RotateCcw } from '@lucide/svelte'
  import { untrack } from 'svelte'
  import { app } from '../../lib/app.svelte'
  import { errorMessage, py } from '../../lib/bridge'
  import ReplaceStage from '../../lib/components/ReplaceStage.svelte'
  import SeasonBadge from '../../lib/components/SeasonBadge.svelte'
  import Segmented from '../../lib/components/Segmented.svelte'
  import { cardsOfPid, pidOf } from '../../lib/meta.svelte'
  import type { FaceFile, FaceKind, ImageInfo, Player, ReplaceResult } from '../../lib/types'
  import { confirmReplace, replaceFace, restoreOfficialFace, type Phase } from './faceActions'
  import CardHeader from './CardHeader.svelte'

  interface Props {
    card: Player
    image: ImageInfo | null
    onImage: (image: ImageInfo) => void
    pasteEnabled: boolean
  }

  let { card, image, onImage, pasteEnabled }: Props = $props()

  const SECTIONS: { kind: FaceKind; title: string; hint: string }[] = [
    { kind: 'head', title: '대갈 미페', hint: '얼굴만 크게 나오는 기본 미페' },
    { kind: 'common', title: '공통 미페', hint: '여러 시즌 카드가 함께 쓰는 연도별 미페' },
    { kind: 'card', title: '카드 미페', hint: '특정 시즌 카드 전용 미페' },
  ]

  type View = 'current' | 'official'
  let faces = $state.raw<FaceFile[] | null>(null)
  let loadedPid: number | null = null
  let focusedSpid: number | null = null
  let request = 0
  let loadError = $state('')
  let selectedRelative = $state<string | null>(null)
  let view = $state<View>('current')
  let flipKey = $state(0)
  let phase = $state<Phase>('idle')

  const pid = $derived(pidOf(card.id))
  const selected = $derived(faces?.find((f) => f.relative === selectedRelative) ?? null)
  const preview = $derived(view === 'current' ? (selected?.currentUrl ?? null) : (selected?.officialUrl ?? null))

  // 선수가 바뀌거나 게임 파일이 바뀌면 후보 목록을 다시 받는다
  $effect(() => {
    void app.revision
    const requestPid = pid
    const name = untrack(() => card.name)
    const id = ++request
    if (requestPid !== loadedPid) faces = null // 다른 선수면 이전 목록을 비운다 (교체 직후 갱신은 그대로 둠)
    loadError = ''
    py()
      .then((api) =>
        api.face.catalog(
          requestPid,
          name,
          cardsOfPid(requestPid).map((c) => c.id),
        ),
      )
      .then((result) => {
        if (id !== request) return
        loadedPid = requestPid
        faces = result
      })
      .catch((error) => {
        if (id === request) loadError = errorMessage(error)
      })
  })

  // 카드를 새로 고르면 그 카드가 기본으로 쓰는 미페를 선택 (목록만 갱신될 땐 고른 미페 유지)
  $effect(() => {
    const spid = card.id
    if (!faces) return
    const list = faces
    untrack(() => {
      if (spid === focusedSpid && list.some((f) => f.relative === selectedRelative)) return
      focusedSpid = spid
      selectedRelative = (list.find((f) => f.defaultFor.includes(spid)) ?? list[0])?.relative ?? null
    })
  })

  const yearSuffix = (face: FaceFile) => (face.year ? ` '${face.year}` : '')

  /** 목록을 다시 받기 전에 바뀐 이미지로 바로 뒤집는다 */
  function showResult(relative: string, result: ReplaceResult) {
    faces =
      faces?.map((f) =>
        f.relative === relative
          ? { ...f, changedAt: result.changedAt, currentUrl: result.currentUrl ?? f.currentUrl }
          : f,
      ) ?? null
    view = 'current'
    flipKey += 1
  }

  async function apply() {
    const face = selected
    if (phase !== 'idle' || !face || !image) return
    phase = 'confirm'
    try {
      if (!(await confirmReplace(card.name, face.relative, face.defaultFor))) return
      phase = 'apply'
      const result = await replaceFace(face.spid ?? card.id, card.name, image, face.relative)
      if (result) showResult(face.relative, result)
    } finally {
      phase = 'idle'
    }
  }

  async function restoreOfficial() {
    const face = selected
    if (phase !== 'idle' || !face) return
    phase = 'restore'
    try {
      const result = await restoreOfficialFace(face.spid ?? card.id, card.name, face.relative)
      if (result) showResult(face.relative, result)
    } finally {
      phase = 'idle'
    }
  }
</script>

<div class="gallery-mode">
  <CardHeader {card} changedAt={null} />

  <div class="gallery">
    <div class="grid-area">
      {#if loadError}
        <p class="warn-text">미페 목록을 불러오지 못했습니다: {loadError}</p>
      {:else if !faces}
        <p class="faint loading"><LoaderCircle size={14} class="spin" /> 이 선수의 미페를 모으는 중</p>
      {:else}
        {#each SECTIONS as section (section.kind)}
          {@const items = faces.filter((f) => f.kind === section.kind)}
          {#if items.length}
            <section>
              <header>
                <h3>{section.title}</h3>
                <span class="faint">{section.hint}</span>
              </header>
              <div class="tiles">
                {#each items as face (face.relative)}
                  <button
                    type="button"
                    class="tile"
                    class:selected={face.relative === selectedRelative}
                    title={face.relative}
                    onclick={() => (selectedRelative = face.relative)}
                  >
                    <span class="tile-image"><img src={face.currentUrl} alt="" loading="lazy" /></span>
                    <span class="tile-label">
                      {#if face.kind === 'card' && face.spid}
                        <SeasonBadge spid={face.spid} suffix={yearSuffix(face)} />
                      {:else}
                        {face.kind === 'head' ? '대갈' : `공통${yearSuffix(face)}`}
                      {/if}
                    </span>
                    {#if face.defaultFor.length}
                      <span class="tag">기본 {face.defaultFor.length}장</span>
                    {/if}
                    {#if face.changedAt}<span class="dot" title="변경됨 {face.changedAt}"></span>{/if}
                  </button>
                {/each}
              </div>
            </section>
          {/if}
        {/each}
      {/if}
    </div>

    <aside class="compare">
      {#if selected}
        <ReplaceStage
          currentSrc={preview}
          currentLabel={view === 'current' ? '현재 미페' : '공식 미페'}
          {flipKey}
          {image}
          {onImage}
          {pasteEnabled}
          applyLabel="이 미페 교체"
          applying={phase === 'apply'}
          canApply={!!image && phase === 'idle'}
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
            <p class="faint path" title={selected.relative}>{selected.relative}</p>
            {#if selected.changedAt}<p class="changed-text">변경됨 {selected.changedAt}</p>{/if}
          {/snippet}
        </ReplaceStage>
        <div class="compare-actions">
          <button type="button" class="btn" onclick={async () => (await py()).app.reveal_game_file(selected.relative)}>
            <FolderOpen size={15} /> 파일 위치 열기
          </button>
          <button type="button" class="btn" disabled={phase !== 'idle'} onclick={restoreOfficial}>
            <RotateCcw size={15} /> 공식 미페로 복원
          </button>
        </div>
      {:else if faces}
        <p class="faint">바꿀 미페를 왼쪽에서 고르세요.</p>
      {/if}
    </aside>
  </div>
</div>

<style>
  .gallery-mode {
    display: grid;
    align-content: start;
    gap: 14px;
    container-type: inline-size;
  }

  .gallery {
    display: grid;
    grid-template-columns: minmax(0, 1fr) clamp(380px, 52%, 460px);
    align-items: start;
    gap: 16px;
  }

  .grid-area {
    display: grid;
    gap: 18px;
    min-width: 0;
  }

  .loading {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  section header {
    display: flex;
    align-items: baseline;
    gap: 10px;
    margin-bottom: 8px;
  }

  h3 {
    font-size: var(--text-md);
    font-weight: 700;
  }

  .tiles {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(96px, 1fr));
    gap: 8px;
  }

  .tile {
    position: relative;
    display: grid;
    gap: 6px;
    padding: 6px 6px 8px;
    border: 1px solid var(--line);
    border-radius: var(--radius-frame);
    background: var(--surface);
    text-align: center;
    cursor: pointer;
    transition:
      border-color 0.15s,
      background 0.15s,
      transform 0.15s var(--ease-out);
  }

  .tile:hover {
    border-color: var(--line-strong);
    background: var(--surface-2);
  }

  .tile.selected {
    border-color: var(--gold);
    background: var(--gold-soft);
  }

  .tile-image {
    aspect-ratio: 1;
    border-radius: 8px;
    background: var(--surface-2);
    overflow: hidden;
  }

  .tile-image img {
    width: 100%;
    height: 100%;
    object-fit: contain;
  }

  .tile-label {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    min-width: 0;
    font-size: var(--text-xs);
    font-weight: 600;
    color: var(--text-2);
    white-space: nowrap;
    overflow: hidden;
  }

  .tag {
    position: absolute;
    top: 10px;
    left: 10px;
    padding: 1px 6px;
    border-radius: 999px;
    background: var(--scrim);
    color: var(--gold);
    font-size: 11px;
    font-weight: 700;
  }

  .dot {
    position: absolute;
    top: 12px;
    right: 12px;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--warn);
    box-shadow: 0 0 0 2px var(--surface);
  }

  .compare {
    position: sticky;
    top: 0;
    display: grid;
    gap: 10px;
  }

  .compare-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .path {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    user-select: text;
  }

  /* 좁으면 비교 패널을 목록 위로 */
  @container (max-width: 700px) {
    .gallery {
      grid-template-columns: minmax(0, 1fr);
    }

    .compare {
      position: static;
      order: -1;
    }
  }
</style>
