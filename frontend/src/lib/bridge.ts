// pywebview가 노출하는 파이썬 API (src/app/api.py) 연결

import type {
  Bootstrap,
  CrestInfo,
  FaceFile,
  FaceTarget,
  HistoryData,
  ImageInfo,
  Manager,
  ManagerInfo,
  Progress,
  ReplaceResult,
  Season,
  Settings,
  SyncResult,
  UpdateInfo,
} from './types'

interface PyApi {
  app: {
    bootstrap(): Promise<Bootstrap>
    seasons(): Promise<Season[]>
    build_db(missing: string[]): Promise<void>
    check_update(): Promise<UpdateInfo | null>
    install_update(downloadUrl: string): Promise<void>
    open_url(url: string): Promise<void>
    reveal(path: string): Promise<void>
    reveal_game_file(relative: string): Promise<void>
    pick_folder(initial: string): Promise<string | null>
    pick_image(): Promise<ImageInfo | null>
    upload_image(name: string, dataBase64: string): Promise<ImageInfo>
  }
  face: {
    resolve(spid: number, name: string): Promise<FaceTarget>
    thumbnails(pid: number, name: string, spids: number[]): Promise<Record<string, string | null>>
    catalog(pid: number, name: string, spids: number[]): Promise<FaceFile[]>
    replace(spid: number, name: string, imagePath: string, relative: string): Promise<ReplaceResult>
    restore_official(spid: number, name: string, relative: string): Promise<ReplaceResult>
  }
  crest: {
    parse_id(text: string): Promise<number | null>
    info(crestId: number): Promise<CrestInfo>
    replace(crestId: number, imagePath: string): Promise<CrestInfo>
  }
  manager: {
    entries(): Promise<Manager[]>
    info(managerId: string): Promise<ManagerInfo>
    thumbnails(managerIds: string[]): Promise<Record<string, string | null>>
    replace(managerId: string, name: string, team: string, imagePath: string): Promise<ManagerInfo>
    restore_official(managerId: string, name: string, team: string): Promise<ManagerInfo>
  }
  history: {
    entries(): Promise<HistoryData>
    restore_face(spid: number): Promise<void>
    delete_face_records(spid: number, positions: number[] | null): Promise<void>
    restore_crest(crestId: number): Promise<void>
    restore_manager(managerId: string): Promise<void>
    delete_manager_record(managerId: string): Promise<void>
  }
  settings: {
    save(values: Partial<Settings>): Promise<{ settings: Settings; pathValid: boolean }>
    sync_meta(): Promise<SyncResult>
  }
}

interface PyWebview {
  api: PyApi
  state: EventTarget & Record<string, unknown>
}

declare global {
  interface Window {
    pywebview?: PyWebview
  }
}

const ready: Promise<PyWebview> = new Promise((resolve) => {
  if (window.pywebview?.api) resolve(window.pywebview)
  else window.addEventListener('pywebviewready', () => resolve(window.pywebview!), { once: true })
})

/** 파이썬 API — `(await py()).face.resolve(...)` */
export async function py(): Promise<PyApi> {
  return (await ready).api
}

/** 파이썬이 window.state.progress 를 바꿀 때마다 호출. 반환값으로 구독 해제. */
export function onProgress(handler: (progress: Progress) => void): () => void {
  const listener = (event: Event) => {
    const { key, value } = (event as CustomEvent<{ key: string; value: unknown }>).detail
    if (key === 'progress') handler(value as Progress)
  }
  let disposed = false
  void ready.then((webview) => {
    if (!disposed) webview.state.addEventListener('change', listener)
  })
  return () => {
    disposed = true
    window.pywebview?.state.removeEventListener('change', listener)
  }
}

/** 예외 메시지 (파이썬 예외는 message에 원문이 그대로 담겨 온다) */
export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}
