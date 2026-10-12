<script lang="ts">
  import { UserRound } from '@lucide/svelte'
  import EmptyState from '../../lib/components/EmptyState.svelte'
  import ImageDrop from '../../lib/components/ImageDrop.svelte'
  import Segmented from '../../lib/components/Segmented.svelte'
  import { parseFaceFileName } from '../../lib/meta.svelte'
  import type { ImageInfo, Player } from '../../lib/types'
  import CardMode from './CardMode.svelte'
  import GalleryMode from './GalleryMode.svelte'
  import PlayerSearch from './PlayerSearch.svelte'

  let { active }: { active: boolean } = $props()

  type Mode = 'card' | 'gallery'
  let mode = $state<Mode>('card')
  let card = $state<Player | null>(null)
  let image = $state<ImageInfo | null>(null)
  let search = $state<ReturnType<typeof PlayerSearch>>()

  function onImage(info: ImageInfo) {
    image = info
    // p{spid}.png 형식이면 그 선수를 찾아 카드까지 자동 선택
    const found = parseFaceFileName(info.name)
    if (found) void search?.showPlayer(found.pid, found.spid)
  }
</script>

<div class="split-page">
  <PlayerSearch bind:this={search} selectedSpid={card?.id ?? null} onSelect={(c) => (card = c)} />

  <div class="workspace">
    <div class="mode-bar">
      <Segmented
        label="교체 방식"
        options={[
          { value: 'card', label: '카드별 교체' },
          { value: 'gallery', label: '전체 미페' },
        ]}
        value={mode}
        onChange={(m) => (mode = m)}
      />
      <p class="faint">
        {mode === 'card'
          ? '선택한 카드가 기본으로 쓰는 미페를 바꿉니다.'
          : '인게임에서 미페를 직접 골라 쓰고 있다면, 화면에 보이는 미페를 찾아 바꾸세요.'}
      </p>
    </div>

    {#if !card}
      <EmptyState icon={UserRound} title="선수를 선택하세요">
        <p class="muted">
          왼쪽에서 선수를 검색해 카드를 고르거나,<br />p&#123;SPID&#125;.png 이름의 이미지를 넣으면 자동으로 찾습니다.
        </p>
        <div class="early-drop"><ImageDrop {image} {onImage} pasteEnabled={active} /></div>
      </EmptyState>
    {:else if mode === 'card'}
      <CardMode {card} {image} {onImage} pasteEnabled={active} />
    {:else}
      <GalleryMode {card} {image} {onImage} pasteEnabled={active} />
    {/if}
  </div>
</div>

<style>
  .mode-bar {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px 14px;
  }

  .early-drop {
    width: 200px;
    margin-top: 10px;
  }
</style>
