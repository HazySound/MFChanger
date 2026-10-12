<script lang="ts">
  import { ArrowRight, LoaderCircle } from '@lucide/svelte'
  import type { Snippet } from 'svelte'
  import type { ImageInfo } from '../types'
  import FaceFrame from './FaceFrame.svelte'
  import ImageDrop from './ImageDrop.svelte'

  interface Props {
    currentSrc: string | null
    currentLabel: string
    currentPlaceholder?: string
    flipKey: number
    /** 현재 이미지 위의 도구 (현재/공식 전환 등) */
    currentTools?: Snippet
    /** 현재 이미지 아래 설명 (게임 파일 경로 등) */
    currentCaption?: Snippet
    image: ImageInfo | null
    onImage: (image: ImageInfo) => void
    pasteEnabled?: boolean
    applyLabel: string
    applying: boolean
    canApply: boolean
    onApply: () => void
  }

  let {
    currentSrc,
    currentLabel,
    currentPlaceholder,
    flipKey,
    currentTools,
    currentCaption,
    image,
    onImage,
    pasteEnabled,
    applyLabel,
    applying,
    canApply,
    onApply,
  }: Props = $props()
</script>

<section class="stage">
  <div class="pitch">
    <div class="side">
      <div class="side-head">
        <h3>{currentLabel}</h3>
        {@render currentTools?.()}
      </div>
      <FaceFrame src={currentSrc} alt={currentLabel} placeholder={currentPlaceholder} {flipKey} />
      {@render currentCaption?.()}
    </div>

    <div class="halfway" aria-hidden="true">
      <span class="circle"><ArrowRight size={18} /></span>
    </div>

    <div class="side">
      <div class="side-head">
        <h3>교체할 이미지</h3>
      </div>
      <ImageDrop {image} {onImage} {pasteEnabled} />
    </div>
  </div>

  <button type="button" class="btn primary large apply" disabled={!canApply || applying} onclick={onApply}>
    {#if applying}
      <LoaderCircle size={18} class="spin" /> 교체하는 중
    {:else}
      {applyLabel}
    {/if}
  </button>
</section>

<style>
  .stage {
    container-type: inline-size;
    display: grid;
    gap: 14px;
  }

  /* 두 이미지 사이를 경기장 하프라인과 센터서클로 나눈다 */
  .pitch {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 56px minmax(0, 1fr);
    align-items: start;
    padding: 18px 20px 20px;
    border-radius: var(--radius-panel);
    border: 1px solid var(--line);
    background:
      linear-gradient(var(--chalk), var(--chalk)) center / 1px 100% no-repeat,
      var(--surface);
  }

  .side {
    display: grid;
    gap: 10px;
    min-width: 0;
    max-width: 300px;
    width: 100%;
    justify-self: center;
  }

  .side-head {
    display: flex;
    flex-wrap: wrap; /* 좁으면 도구(현재/공식 전환)가 제목 아래로 */
    align-items: center;
    justify-content: space-between;
    gap: 6px 8px;
    min-height: 36px;
  }

  h3 {
    white-space: nowrap;
    font-size: var(--text-sm);
    font-weight: 600;
    color: var(--text-2);
  }

  .halfway {
    display: grid;
    place-items: center;
    align-self: center;
  }

  .circle {
    display: grid;
    place-items: center;
    width: 44px;
    height: 44px;
    border-radius: 50%;
    border: 1px solid var(--line-strong);
    background: var(--bg);
    color: var(--text-3);
  }

  .apply {
    width: 100%;
  }

  /* 두 이미지를 나란히 둘 수 없을 만큼 좁으면 위아래로 */
  @container (max-width: 340px) {
    .pitch {
      grid-template-columns: minmax(0, 1fr);
      gap: 4px;
      background:
        linear-gradient(var(--chalk), var(--chalk)) center / 100% 1px no-repeat,
        var(--surface);
    }

    .halfway :global(svg) {
      transform: rotate(90deg);
    }
  }
</style>
