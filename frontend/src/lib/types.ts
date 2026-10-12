// 파이썬 API(src/app/api.py)와 주고받는 데이터 형식

export interface Player {
  id: number
  name: string
}

export interface Season {
  seasonId: number
  className: string
  seasonImg: string
  category: string
  year: string
  shortName: string
}

export interface Settings {
  fc_online_path: string
  backup_enabled: boolean
  backup_path: string
  check_update_on_start: boolean
  zoom: number
}

export interface Bootstrap {
  version: string
  settings: Settings
  pathValid: boolean
  missingDb: string[]
  playersUrl: string
}

export interface UpdateInfo {
  version: string
  url: string
  download_url: string | null
  notes: string
  installable: boolean
}

export interface Progress {
  task: 'db' | 'update'
  label: string
  fraction: number
}

export interface ImageInfo {
  path: string
  name: string
  width: number
  height: number
  url: string
}

/** 카드가 기본으로 쓰는 미페 파일 (데이터센터 기준) */
export interface FaceTarget {
  relative: string
  sharedSpids: number[]
  verified: boolean
  currentUrl: string | null
  officialUrl: string
  changedAt: string | null
}

export type FaceKind = 'head' | 'common' | 'card'

/** 바둑판 모드의 미페 후보 */
export interface FaceFile {
  relative: string
  kind: FaceKind
  spid: number | null
  year: string | null
  defaultFor: number[]
  cached: boolean
  currentUrl: string
  officialUrl: string
  changedAt: string | null
}

export interface ReplaceResult {
  changedAt: string
  currentUrl: string | null
}

export interface CrestInfo {
  id: number
  path: string
  currentUrl: string | null
  changedAt: string | null
}

export interface Manager {
  id: string
  name: string
  team: string
}

export interface ManagerInfo {
  fileName: string
  path: string
  currentUrl: string | null
  officialUrl: string
  usesGeneric: boolean
  changedAt: string | null
}

export interface FaceHistoryEntry {
  position: number
  source: string
  changedAt: string
  beforeUrl: string | null
  afterUrl: string | null
  hasBackup: boolean
}

export interface FaceHistoryGroup {
  spid: number
  playerName: string
  backupDir: string
  entries: FaceHistoryEntry[]
}

export interface CrestHistoryRow {
  crestId: number
  source: string
  changedAt: string
  beforeUrl: string | null
  afterUrl: string | null
  hasBackup: boolean
  backupDir: string
}

export interface ManagerHistoryRow {
  managerId: string
  name: string
  team: string
  source: string
  changedAt: string
  currentUrl: string | null
}

export interface HistoryData {
  faces: FaceHistoryGroup[]
  crests: CrestHistoryRow[]
  managers: ManagerHistoryRow[]
}

export interface SyncResult {
  spid: number
  seasons: number
  managers: number | null
  managers_error: string | null
}
