// 앱 전역 상태 — 설정, 경로 상태, 업데이트, 진행 화면, 변경 알림

import { errorMessage, onProgress, py } from './bridge'
import type { Settings, UpdateInfo } from './types'

export const HELP_URL = 'https://github.com/HazySound/MFChanger'

export interface Overlay {
  title: string
  label: string
  fraction: number
  note: string
}

export const app = $state({
  version: '',
  /** 선수 목록 주소 (데이터 동기화 후 다시 읽을 때도 사용) */
  playersUrl: '',
  settings: null as Settings | null,
  pathValid: true,
  update: null as UpdateInfo | null,
  /** 업데이트 설치 실패 사유 (배너와 설정 탭에 표시) */
  updateError: '',
  /** 화면 전체를 덮는 진행 화면 (DB 생성, 업데이트 설치) */
  overlay: null as Overlay | null,
  /**
   * 게임 파일이나 변경 이력이 바뀔 때마다 증가 — 다른 탭이 이 값을 보고 화면을 새로 읽는다.
   * (예: 이력에서 복원하면 미페 탭 미리보기·썸네일 갱신)
   */
  revision: 0,
})

export function markChanged() {
  app.revision += 1
}

export async function saveSettings(values: Partial<Settings>) {
  const result = await (await py()).settings.save(values)
  app.settings = result.settings
  app.pathValid = result.pathValid
}

/** 새 버전 확인 — 결과는 app.update (최신이면 null) */
export async function checkUpdate() {
  app.update = await (await py()).app.check_update()
  app.updateError = ''
  return app.update
}

/**
 * 진행 화면을 띄운 채 작업 실행. 파이썬이 보내는 진행률(task 일치)로 화면을 갱신한다.
 * 작업이 끝나거나 실패하면 진행 화면을 닫는다 (실패는 예외로 올림).
 */
export async function withOverlay<T>(
  task: 'db' | 'update',
  overlay: Omit<Overlay, 'fraction'>,
  work: () => Promise<T>,
): Promise<T> {
  app.overlay = { ...overlay, fraction: 0 }
  const unsubscribe = onProgress((progress) => {
    if (progress.task === task && app.overlay) {
      app.overlay.label = progress.label
      app.overlay.fraction = progress.fraction
    }
  })
  try {
    return await work()
  } finally {
    unsubscribe()
    app.overlay = null
  }
}

/** 업데이트 다운로드 → 설치. 성공하면 파이썬이 새 버전을 실행하고 이 창을 닫는다. */
export async function installUpdate() {
  const url = app.update?.download_url
  if (!url) return
  app.updateError = ''
  try {
    await withOverlay(
      'update',
      {
        title: '업데이트 다운로드 중',
        label: '준비 중',
        note: '완료되면 자동으로 다시 시작합니다. 프로그램을 끄지 마세요.',
      },
      async () => {
        await (await py()).app.install_update(url)
        // 창이 닫힐 때까지 진행 화면 유지
        await new Promise(() => {})
      },
    )
  } catch (error) {
    app.updateError = errorMessage(error)
  }
}
