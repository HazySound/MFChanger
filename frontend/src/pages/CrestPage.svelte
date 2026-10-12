<script lang="ts">
  import { ExternalLink, FolderOpen } from '@lucide/svelte'
  import { markChanged } from '../lib/app.svelte'
  import { py } from '../lib/bridge'
  import ReplaceStage from '../lib/components/ReplaceStage.svelte'
  import { toast, toastError } from '../lib/notify.svelte'
  import type { CrestInfo, ImageInfo } from '../lib/types'

  let { active }: { active: boolean } = $props()

  const TEAMCOLOR_URL = 'https://fconline.nexon.com/datacenter/teamcolor'

  let idText = $state('')
  let crest = $state<CrestInfo | null>(null)
  let status = $state('')
  let image = $state<ImageInfo | null>(null)
  let flipKey = $state(0)
  let applying = $state(false)

  /** 입력값(또는 파일명)을 크레스트 ID로 해석해 현재 크레스트를 불러온다 */
  async function loadCrest(text: string) {
    const api = await py()
    const id = await api.crest.parse_id(text)
    if (id === null) {
      status = '크레스트 ID를 숫자로 입력해주세요. (예: 1234, d1234, l1234.png)'
      return
    }
    idText = String(id)
    try {
      crest = await api.crest.info(id)
      status = crest.currentUrl ? '' : `ID ${id}의 크레스트 파일이 게임 폴더에 없습니다.`
    } catch (error) {
      crest = null
      status = ''
      toastError(error)
    }
  }

  async function onImage(info: ImageInfo) {
    image = info
    // 1234.png / d1234.png / l1234.png 이면 ID 자동 인식
    if ((await (await py()).crest.parse_id(info.name)) !== null) await loadCrest(info.name)
  }

  async function apply() {
    if (!crest || !image) return
    applying = true
    try {
      crest = await (await py()).crest.replace(crest.id, image.path)
      status = ''
      flipKey += 1
      toast('크레스트를 교체했습니다.')
      markChanged()
    } catch (error) {
      toastError(error)
    } finally {
      applying = false
    }
  }
</script>

<div class="crest-page">
  <div class="lookup panel">
    <div class="lookup-row">
      <form
        class="id-form"
        onsubmit={(e) => {
          e.preventDefault()
          void loadCrest(idText)
        }}
      >
        <label for="crest-id">크레스트 ID</label>
        <input id="crest-id" class="field" placeholder="예: 1234" bind:value={idText} />
        <button type="submit" class="btn">미리보기</button>
      </form>
      <div class="lookup-actions">
        <button type="button" class="btn ghost" onclick={async () => (await py()).app.open_url(TEAMCOLOR_URL)}>
          <ExternalLink size={15} /> ID 찾기
        </button>
        <button
          type="button"
          class="btn"
          disabled={!crest}
          onclick={async () => crest && (await py()).app.reveal(crest.path)}
        >
          <FolderOpen size={15} /> 파일 위치 열기
        </button>
      </div>
    </div>
    <p class="faint">
      팀컬러 페이지에서 엠블럼 이미지를 우클릭해 다른 이름으로 저장하고, 그 파일명을 그대로 입력하거나 이미지를 넣으면
      ID를 자동으로 인식합니다.
    </p>
    {#if status}<p class="warn-text">{status}</p>{/if}
    {#if crest?.changedAt}<p class="changed-text">변경됨 {crest.changedAt}</p>{/if}
  </div>

  <ReplaceStage
    currentSrc={crest?.currentUrl ?? null}
    currentLabel="현재 크레스트"
    currentPlaceholder={crest ? '게임 폴더에 파일이 없습니다' : 'ID를 입력하고\n미리보기를 누르세요'}
    {flipKey}
    {image}
    {onImage}
    pasteEnabled={active}
    applyLabel="크레스트 교체"
    {applying}
    canApply={!!crest && !!image}
    onApply={apply}
  />
</div>

<style>
  .crest-page {
    display: grid;
    align-content: start;
    gap: 16px;
    width: 100%; /* 격자 안 margin: auto 는 내용 폭으로 줄어들므로 명시 */
    max-width: 860px;
    margin: 0 auto;
    padding: 16px;
    overflow-y: auto;
  }

  .lookup {
    display: grid;
    gap: 10px;
    padding: 16px 18px;
  }

  .lookup-row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
  }

  .id-form {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  label {
    font-weight: 700;
    white-space: nowrap;
  }

  .id-form .field {
    width: 160px;
  }

  .lookup-actions {
    display: flex;
    gap: 8px;
  }
</style>
