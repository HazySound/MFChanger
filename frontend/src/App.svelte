<script lang="ts">
  import { CircleHelp, TriangleAlert, X } from '@lucide/svelte'
  import { onMount } from 'svelte'
  import { SvelteSet } from 'svelte/reactivity'
  import { slide } from 'svelte/transition'
  import { app, checkUpdate, HELP_URL, installUpdate, withOverlay } from './lib/app.svelte'
  import { errorMessage, py } from './lib/bridge'
  import ConfirmDialog from './lib/components/ConfirmDialog.svelte'
  import ProgressOverlay from './lib/components/ProgressOverlay.svelte'
  import Toasts from './lib/components/Toasts.svelte'
  import { loadMeta } from './lib/meta.svelte'
  import CrestPage from './pages/CrestPage.svelte'
  import FacePage from './pages/face/FacePage.svelte'
  import HistoryPage from './pages/history/HistoryPage.svelte'
  import ManagerPage from './pages/ManagerPage.svelte'
  import SettingsPage from './pages/SettingsPage.svelte'

  const TABS = [
    { id: 'face', label: '미페 변경' },
    { id: 'crest', label: '크레스트 변경' },
    { id: 'manager', label: '감독 변경' },
    { id: 'history', label: '변경 이력' },
    { id: 'settings', label: '설정' },
  ] as const
  type TabId = (typeof TABS)[number]['id']

  let tab = $state<TabId>('face')
  /** 한 번 연 탭은 계속 유지 (입력·선택 상태 보존) */
  const opened = new SvelteSet<TabId>(['face'])
  let bannerClosed = $state(false)
  let missingDb = $state<string[]>([])
  let dbError = $state('')

  const showBanner = $derived(!!app.update && !bannerClosed)

  $effect(() => {
    document.documentElement.style.zoom = String(app.settings?.zoom ?? 1)
  })

  function openTab(id: TabId) {
    tab = id
    opened.add(id)
  }

  async function buildMissingDb() {
    dbError = ''
    try {
      await withOverlay(
        'db',
        {
          title: 'DB 생성 중',
          label: '준비 중',
          note: `총 ${missingDb.length}개 파일을 생성합니다. 잠시만 기다려주세요.`,
        },
        async () => (await py()).app.build_db(missingDb),
      )
      missingDb = []
      await loadMeta(app.playersUrl)
    } catch (error) {
      dbError = errorMessage(error)
    }
  }

  onMount(async () => {
    const boot = await (await py()).app.bootstrap()
    app.version = boot.version
    app.settings = boot.settings
    app.pathValid = boot.pathValid
    app.playersUrl = boot.playersUrl
    missingDb = boot.missingDb

    const updateCheck = boot.settings.check_update_on_start ? checkUpdate().catch(() => {}) : Promise.resolve()
    if (missingDb.length) {
      // DB를 만들 때만 업데이트 확인을 기다린다 — DB 생성 로직이 바뀐 새 버전으로 먼저 업데이트하도록
      await updateCheck
      await buildMissingDb()
    } else {
      await loadMeta(app.playersUrl)
    }
  })
</script>

<div class="shell">
  {#if showBanner && app.update}
    <div class="banner" transition:slide={{ duration: 180 }}>
      <p>
        {#if app.updateError}
          업데이트 설치 실패: {app.updateError}
        {:else}
          새 버전 {app.update.version}이(가) 나왔습니다.
        {/if}
      </p>
      {#if app.update.installable}
        <button type="button" class="btn small primary" onclick={installUpdate}>업데이트 설치</button>
      {/if}
      <button type="button" class="btn small" onclick={async () => (await py()).app.open_url(app.update!.url)}>
        릴리즈 페이지
      </button>
      <button type="button" class="btn ghost small icon" aria-label="알림 닫기" onclick={() => (bannerClosed = true)}>
        <X size={14} />
      </button>
    </div>
  {/if}

  <header>
    <span class="brand">MFChanger</span>
    <nav aria-label="메뉴">
      {#each TABS as item (item.id)}
        <button
          type="button"
          class:active={tab === item.id}
          aria-current={tab === item.id ? 'page' : undefined}
          onclick={() => openTab(item.id)}
        >
          {item.label}
        </button>
      {/each}
    </nav>
    <button type="button" class="btn ghost small" onclick={async () => (await py()).app.open_url(HELP_URL)}>
      <CircleHelp size={15} /> 사용법
    </button>
  </header>

  {#if !app.pathValid && tab !== 'settings'}
    <div class="path-warning" transition:slide={{ duration: 160 }}>
      <TriangleAlert size={16} />
      <p>FC온라인 설치 폴더를 찾을 수 없습니다. 교체하려면 설정에서 설치 경로를 지정해주세요.</p>
      <button type="button" class="btn small" onclick={() => openTab('settings')}>설정 열기</button>
    </div>
  {/if}

  <main>
    {#if dbError}
      <div class="db-error">
        <h2>필요한 DB 파일을 만들지 못했습니다</h2>
        <p class="muted">{dbError}</p>
        <p class="faint">인터넷 연결을 확인한 뒤 다시 시도해주세요.</p>
        <button type="button" class="btn primary" onclick={buildMissingDb}>다시 시도</button>
      </div>
    {:else}
      {#if opened.has('face')}<section hidden={tab !== 'face'}><FacePage active={tab === 'face'} /></section>{/if}
      {#if opened.has('crest')}<section hidden={tab !== 'crest'}><CrestPage active={tab === 'crest'} /></section>{/if}
      {#if opened.has('manager')}<section hidden={tab !== 'manager'}>
          <ManagerPage active={tab === 'manager'} />
        </section>{/if}
      {#if opened.has('history')}<section hidden={tab !== 'history'}>
          <HistoryPage active={tab === 'history'} />
        </section>{/if}
      {#if opened.has('settings')}<section hidden={tab !== 'settings'}><SettingsPage /></section>{/if}
    {/if}
  </main>
</div>

{#if app.overlay}
  <ProgressOverlay {...app.overlay} />
{/if}
<ConfirmDialog />
<Toasts />

<style>
  /* 배너·경로 경고는 있을 때만 나타나므로 격자 행 대신 세로로 쌓고, 화면 영역이 남은 높이를 채운다 */
  .shell {
    display: flex;
    flex-direction: column;
    height: 100%;
  }

  .banner {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px 8px 20px;
    background: var(--gold-soft);
    border-bottom: 1px solid rgb(242 201 76 / 0.35);
  }

  .banner p {
    flex: 1;
    font-size: var(--text-sm);
    font-weight: 600;
    color: var(--gold);
  }

  header {
    display: flex;
    align-items: center;
    gap: 28px;
    padding: 0 16px 0 22px;
    height: 56px;
    border-bottom: 1px solid var(--line);
  }

  .brand {
    font-size: var(--text-lg);
    font-weight: 800;
    letter-spacing: -0.02em;
  }

  nav {
    display: flex;
    flex: 1;
    align-self: stretch;
    gap: 4px;
    min-width: 0;
    overflow: hidden; /* 밑줄(::after)이 1px 내려와도 스크롤바가 생기지 않게 */
  }

  nav button {
    position: relative;
    padding: 0 12px;
    border: 0;
    background: none;
    color: var(--text-2);
    font-size: var(--text-md);
    font-weight: 600;
    white-space: nowrap;
    cursor: pointer;
    transition: color 0.15s;
  }

  nav button:hover {
    color: var(--text);
  }

  nav button.active {
    color: var(--text);
  }

  nav button::after {
    content: '';
    position: absolute;
    left: 12px;
    right: 12px;
    bottom: -1px;
    height: 2px;
    border-radius: 2px;
    background: var(--gold);
    transform: scaleX(0);
    transition: transform 0.22s var(--ease-out);
  }

  nav button.active::after {
    transform: scaleX(1);
  }

  .path-warning {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 16px 8px 22px;
    background: rgb(233 162 59 / 0.1);
    border-bottom: 1px solid rgb(233 162 59 / 0.3);
    color: var(--warn);
  }

  .path-warning p {
    flex: 1;
    font-size: var(--text-sm);
  }

  main {
    flex: 1;
    display: grid;
    grid-template-rows: minmax(0, 1fr);
    min-height: 0;
  }

  /* 탭 화면이 남은 높이를 정확히 채우도록 (각 화면은 안에서 스크롤) */
  main > section {
    display: grid;
    grid-template-rows: minmax(0, 1fr);
    min-height: 0;
  }

  main > section[hidden] {
    display: none;
  }

  .db-error {
    display: grid;
    justify-items: center;
    align-content: center;
    gap: 8px;
    text-align: center;
  }

  .db-error .btn {
    margin-top: 10px;
  }
</style>
