<script lang="ts">
  import { ImagePlus } from '@lucide/svelte'
  import { py } from '../bridge'
  import { toastError } from '../notify.svelte'
  import type { ImageInfo } from '../types'

  interface Props {
    image: ImageInfo | null
    onImage: (image: ImageInfo) => void
    /** 이 영역이 보이는 동안만 Ctrl+V 붙여넣기를 받는다 */
    pasteEnabled?: boolean
  }

  let { image, onImage, pasteEnabled = true }: Props = $props()

  let dragging = $state(false)
  let busy = $state(false)
  const square = $derived(!image || image.width === image.height)

  async function receive(load: () => Promise<ImageInfo | null>) {
    busy = true
    try {
      const info = await load()
      if (info) onImage(info)
    } catch (error) {
      toastError(error)
    } finally {
      busy = false
    }
  }

  function readBase64(file: File): Promise<string> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => resolve(String(reader.result).split(',', 2)[1])
      reader.onerror = () => reject(reader.error)
      reader.readAsDataURL(file)
    })
  }

  function upload(file: File, name = file.name) {
    void receive(async () => (await py()).app.upload_image(name, await readBase64(file)))
  }

  function pick() {
    void receive(async () => (await py()).app.pick_image())
  }

  function onDrop(event: DragEvent) {
    dragging = false
    const file = event.dataTransfer?.files[0]
    if (file) upload(file)
  }

  function onPaste(event: ClipboardEvent) {
    // 입력창에 글자를 붙여넣는 중이면 무시
    if (!pasteEnabled || (event.target instanceof Element && event.target.closest('input, textarea'))) return
    const file = [...(event.clipboardData?.files ?? [])].find((f) => f.type.startsWith('image/'))
    if (!file) return
    event.preventDefault()
    upload(file, file.name || 'clipboard.png')
  }
</script>

<svelte:window onpaste={onPaste} />

<div class="drop">
  <button
    type="button"
    class="zone"
    class:dragging
    class:filled={!!image}
    disabled={busy}
    onclick={pick}
    ondragenter={() => (dragging = true)}
    ondragleave={() => (dragging = false)}
    ondrop={onDrop}
  >
    {#if image}
      <img src={image.url} alt={image.name} draggable="false" />
    {:else}
      <ImagePlus size={28} strokeWidth={1.6} />
      <span>이미지를 끌어다 놓거나<br />클릭해서 선택</span>
    {/if}
  </button>

  {#if image}
    <p class="faint name" title={image.name}>{image.name} ({image.width}×{image.height}px)</p>
    {#if !square}
      <p class="warn-text">정사각형이 아니라서 가운데를 기준으로 잘립니다.</p>
    {/if}
  {:else}
    <p class="faint">JPG, PNG, BMP, WEBP 지원<br />Ctrl+V로 붙여넣기 가능</p>
  {/if}
</div>

<style>
  .drop {
    display: grid;
    gap: 6px;
    min-width: 0;
  }

  .zone {
    position: relative;
    display: grid;
    place-items: center;
    align-content: center;
    gap: 10px;
    width: 100%;
    aspect-ratio: 1;
    padding: 0;
    border: 1.5px dashed var(--line-strong);
    border-radius: var(--radius-frame);
    background: var(--surface-2);
    color: var(--text-3);
    font-size: var(--text-sm);
    line-height: 1.45;
    text-align: center;
    overflow: hidden;
    cursor: pointer;
    transition:
      border-color 0.15s,
      background 0.15s,
      color 0.15s;
  }

  .zone:hover,
  .zone.dragging {
    border-color: var(--gold);
    color: var(--text-2);
  }

  .zone.dragging {
    background: var(--gold-soft);
  }

  .zone.filled {
    border-style: solid;
    border-color: var(--line);
  }

  .zone:disabled {
    cursor: progress;
    opacity: 0.6;
  }

  img {
    width: 100%;
    height: 100%;
    object-fit: contain;
  }

  .name {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
</style>
