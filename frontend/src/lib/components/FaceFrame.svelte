<script lang="ts">
  import { cubicOut } from 'svelte/easing'

  interface Props {
    src: string | null
    alt?: string
    placeholder?: string
    /** 값이 바뀔 때마다 카드가 뒤집히며 새 이미지를 보여준다 (교체 직후) */
    flipKey?: number
  }

  let { src, alt = '', placeholder = '이미지 없음', flipKey = 0 }: Props = $props()

  let failedSrc = $state<string | null>(null)
  const showImage = $derived(!!src && src !== failedSrc)

  function flipIn(_node: Element, { duration = 520 } = {}) {
    return {
      duration,
      css: (t: number) => {
        const eased = cubicOut(t)
        return `transform: perspective(700px) rotateY(${(1 - eased) * 180}deg); opacity: ${t < 0.5 ? 0 : 1}`
      },
    }
  }
</script>

<div class="frame">
  {#key flipKey}
    <div class="face" in:flipIn>
      {#if showImage}
        <img {src} {alt} draggable="false" onerror={() => (failedSrc = src)} />
      {:else}
        <span class="placeholder">{placeholder}</span>
      {/if}
    </div>
  {/key}
</div>

<style>
  .frame {
    position: relative;
    width: 100%;
    aspect-ratio: 1;
    border-radius: var(--radius-frame);
    background: var(--surface-2);
    border: 1px solid var(--line);
    overflow: hidden;
  }

  .face {
    position: absolute;
    inset: 0;
    display: grid;
    place-items: center;
    backface-visibility: hidden;
  }

  img {
    width: 100%;
    height: 100%;
    object-fit: contain;
  }

  .placeholder {
    padding: 12px;
    color: var(--text-3);
    font-size: var(--text-sm);
    text-align: center;
    white-space: pre-line;
  }
</style>
