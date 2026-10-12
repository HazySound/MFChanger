<script lang="ts">
  import { CircleCheck, CircleAlert, FolderOpen, LoaderCircle } from '@lucide/svelte'
  import { untrack } from 'svelte'
  import { app, checkUpdate, installUpdate, markChanged, saveSettings } from '../lib/app.svelte'
  import { errorMessage, py } from '../lib/bridge'
  import Segmented from '../lib/components/Segmented.svelte'
  import Switch from '../lib/components/Switch.svelte'
  import { loadMeta } from '../lib/meta.svelte'
  import { toast, toastError } from '../lib/notify.svelte'
  import type { Settings } from '../lib/types'

  const ZOOM_OPTIONS = [
    { value: '0.9', label: '90%' },
    { value: '1', label: '100%' },
    { value: '1.1', label: '110%' },
    { value: '1.25', label: '125%' },
  ]

  let fcPath = $state('')
  let backupPath = $state('')
  let filled = false

  // 설정을 받은 뒤 한 번만 입력란을 채운다 (이후엔 사용자가 고친 값을 유지)
  $effect(() => {
    const settings = app.settings
    if (!settings || filled) return
    filled = true
    untrack(() => {
      fcPath = settings.fc_online_path
      backupPath = settings.backup_path
    })
  })
  let syncing = $state(false)
  let syncResult = $state<{ ok: boolean; text: string } | null>(null)
  let checking = $state(false)
  let updateChecked = $state(false)

  async function save(values: Partial<Settings>, message?: string) {
    try {
      await saveSettings(values)
      if ('fc_online_path' in values) markChanged() // 열려 있는 미리보기·썸네일을 새 경로 기준으로
      if (message) toast(message)
    } catch (error) {
      toastError(error)
    }
  }

  async function browse(current: string): Promise<string | null> {
    return (await py()).app.pick_folder(current)
  }

  async function sync() {
    syncing = true
    syncResult = null
    try {
      const result = await (await py()).settings.sync_meta()
      const base = `선수 ${result.spid.toLocaleString()}명, 시즌 ${result.seasons}개`
      syncResult =
        result.managers !== null
          ? { ok: true, text: `동기화 완료: ${base}, 감독 ${result.managers}명` }
          : { ok: false, text: `${base}는 동기화했지만 감독 정보 갱신에 실패했습니다: ${result.managers_error}` }
      await loadMeta(app.playersUrl)
      markChanged()
    } catch (error) {
      syncResult = { ok: false, text: `동기화 실패: ${errorMessage(error)}` }
    } finally {
      syncing = false
    }
  }

  async function check() {
    checking = true
    try {
      await checkUpdate()
      updateChecked = true
    } catch (error) {
      toastError(error)
    } finally {
      checking = false
    }
  }
</script>

<div class="settings-page">
  <h1>설정</h1>

  <section class="panel">
    <h2>FC온라인 설치 경로</h2>
    <div class="path-row">
      <input class="field" bind:value={fcPath} spellcheck="false" />
      <button type="button" class="btn" onclick={async () => (fcPath = (await browse(fcPath)) ?? fcPath)}>
        <FolderOpen size={15} /> 폴더 선택
      </button>
      <button
        type="button"
        class="btn primary"
        onclick={() => save({ fc_online_path: fcPath.trim() }, '설치 경로를 저장했습니다.')}
      >
        저장
      </button>
    </div>
    <p class="state" class:bad={!app.pathValid}>
      {#if app.pathValid}<CircleCheck size={15} /> 게임 리소스 폴더를 찾았습니다.
      {:else}<CircleAlert size={15} /> 이 경로에서 게임 리소스 폴더(_cache)를 찾을 수 없습니다.{/if}
    </p>
  </section>

  <section class="panel">
    <h2>백업</h2>
    <Switch
      label="교체하기 전 원본 파일 자동 백업"
      checked={app.settings?.backup_enabled ?? true}
      onChange={(on) => save({ backup_enabled: on })}
    />
    <label class="sub-label" for="backup-path">백업 저장 위치</label>
    <div class="path-row">
      <input id="backup-path" class="field" bind:value={backupPath} spellcheck="false" />
      <button type="button" class="btn" onclick={async () => (backupPath = (await browse(backupPath)) ?? backupPath)}>
        <FolderOpen size={15} /> 폴더 선택
      </button>
      <button
        type="button"
        class="btn primary"
        onclick={() => save({ backup_path: backupPath.trim() }, '백업 경로를 저장했습니다.')}
      >
        저장
      </button>
    </div>
  </section>

  <section class="panel">
    <h2>화면 배율</h2>
    <Segmented
      label="화면 배율"
      options={ZOOM_OPTIONS}
      value={String(app.settings?.zoom ?? 1)}
      onChange={(v) => save({ zoom: Number(v) })}
    />
  </section>

  <section class="panel">
    <h2>선수 데이터</h2>
    <div class="action-row">
      <button type="button" class="btn" disabled={syncing} onclick={sync}>
        {#if syncing}<LoaderCircle size={15} class="spin" /> 동기화하는 중{:else}데이터 동기화{/if}
      </button>
      <p class="muted">선수·시즌·감독 정보를 최신으로 받습니다. 기존 데이터는 백업 폴더에 보관합니다.</p>
    </div>
    {#if syncResult}<p class="state" class:bad={!syncResult.ok}>{syncResult.text}</p>{/if}
  </section>

  <section class="panel">
    <h2>업데이트</h2>
    <Switch
      label="시작할 때 새 버전 확인"
      checked={app.settings?.check_update_on_start ?? true}
      onChange={(on) => save({ check_update_on_start: on })}
    />
    <div class="action-row">
      <button type="button" class="btn" disabled={checking} onclick={check}>
        {#if checking}<LoaderCircle size={15} class="spin" /> 확인하는 중{:else}업데이트 확인{/if}
      </button>
      {#if app.update?.installable}
        <button type="button" class="btn primary" onclick={installUpdate}>업데이트 설치</button>
      {/if}
      {#if app.update}
        <button type="button" class="btn" onclick={async () => (await py()).app.open_url(app.update!.url)}
          >릴리즈 페이지</button
        >
      {/if}
    </div>
    <p
      class="state"
      class:bad={!!app.updateError}
      class:news={!!app.update && !app.updateError}
      class:neutral={!app.update && !app.updateError && !updateChecked}
    >
      {#if app.updateError}설치 실패: {app.updateError}
      {:else if app.update}새 버전 {app.update.version}이(가) 있습니다. (현재 v{app.version})
      {:else if updateChecked}최신 버전입니다. (v{app.version})
      {:else}현재 버전 v{app.version}{/if}
    </p>
  </section>
</div>

<style>
  .settings-page {
    display: grid;
    align-content: start;
    gap: 14px;
    width: 100%; /* 격자 안 margin: auto 는 내용 폭으로 줄어들므로 명시 */
    max-width: 760px;
    margin: 0 auto;
    padding: 16px 20px 28px;
    overflow-y: auto;
  }

  h1 {
    font-size: var(--text-xl);
    font-weight: 800;
    margin-bottom: 4px;
  }

  section {
    display: grid;
    gap: 12px;
    padding: 18px 20px;
  }

  .path-row,
  .action-row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
  }

  .path-row .field {
    flex: 1;
    min-width: 240px;
  }

  .action-row p {
    flex: 1;
    min-width: 220px;
  }

  .sub-label {
    color: var(--text-2);
    font-size: var(--text-sm);
    font-weight: 600;
  }

  .state {
    display: flex;
    align-items: center;
    gap: 6px;
    color: var(--success);
    font-size: var(--text-sm);
  }

  .state.bad {
    color: var(--danger);
  }

  .state.news {
    color: var(--gold);
  }

  .state.neutral {
    color: var(--text-2);
  }
</style>
