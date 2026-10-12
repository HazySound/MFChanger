// 선수·시즌 메타데이터와 검색

import { errorMessage, py } from './bridge'
import type { Player, Season } from './types'

export const CATEGORY_ORDER = ['TOTY', 'TOTS', 'UCL', 'PL', 'LIVE', 'K리그', 'ICON', '기타']
export const ALL_YEARS = '전체'
export const NO_YEAR = '기타'
const MAX_RESULTS = 200

/** spid = 시즌 ID(앞 3자리) + 선수 고유 ID(뒤 6자리) */
export const seasonIdOf = (spid: number) => Math.floor(spid / 1_000_000)
export const pidOf = (spid: number) => spid % 1_000_000

class Meta {
  // 8만 건이 넘는 목록 — 깊은 반응형 프록시 없이 통째로만 교체 ($state.raw)
  players = $state.raw<Player[]>([])
  seasons = $state.raw<Season[]>([])
  seasonMap = $state.raw(new Map<number, Season>())
  loaded = $state(false)
  error = $state('')
}

export const meta = new Meta()

export async function loadMeta(playersUrl: string) {
  meta.error = ''
  try {
    const [players, seasons] = await Promise.all([
      fetch(playersUrl).then((res) => {
        if (!res.ok) throw new Error(`선수 데이터를 읽지 못했습니다 (HTTP ${res.status})`)
        return res.json() as Promise<Player[]>
      }),
      py().then((api) => api.app.seasons()),
    ])
    meta.players = players
    meta.seasons = seasons
    meta.seasonMap = new Map(seasons.map((s) => [s.seasonId, s]))
    meta.loaded = true
  } catch (error) {
    meta.error = errorMessage(error)
  }
}

export function seasonOf(spid: number): Season | undefined {
  return meta.seasonMap.get(seasonIdOf(spid))
}

// ── 시즌 필터 ──

export interface SeasonFilter {
  /** 카테고리 → 선택한 연도('전체', '기타' 포함) */
  categories: Record<string, string[]>
  /** 시즌 이름 검색으로 고른 시즌 — 있으면 카테고리 선택보다 우선 */
  seasonIds: number[]
}

export const emptyFilter = (): SeasonFilter => ({ categories: {}, seasonIds: [] })

export function isFilterActive(filter: SeasonFilter): boolean {
  return filter.seasonIds.length > 0 || Object.keys(filter.categories).length > 0
}

function passesFilter(spid: number, filter: SeasonFilter): boolean {
  if (filter.seasonIds.length) return filter.seasonIds.includes(seasonIdOf(spid))
  if (!Object.keys(filter.categories).length) return true

  const season = seasonOf(spid)
  const years = filter.categories[season?.category ?? '']
  if (!years) return false
  if (years.includes(ALL_YEARS)) return true
  const year = season?.year ?? ''
  return year ? years.includes(year) : years.includes(NO_YEAR)
}

// ── 검색 ──

export interface PlayerGroup {
  pid: number
  name: string
  cards: Player[]
}

const normalize = (text: string) => text.toLowerCase().replaceAll(' ', '')

/** 이름 검색 + 시즌 필터. 둘 다 비어 있으면 빈 결과. */
export function searchCards(query: string, filter: SeasonFilter): Player[] {
  const q = normalize(query.trim())
  if (!q && !isFilterActive(filter)) return []
  return meta.players
    .filter((p) => (!q || normalize(p.name).includes(q)) && passesFilter(p.id, filter))
    .slice(0, MAX_RESULTS)
}

export function cardsOfPid(pid: number): Player[] {
  return meta.players.filter((p) => pidOf(p.id) === pid).slice(0, MAX_RESULTS)
}

/** 같은 선수(pid)의 카드끼리 묶어 이름순 정렬 */
export function groupByPlayer(cards: Player[]): PlayerGroup[] {
  const groups = new Map<number, PlayerGroup>()
  for (const card of cards) {
    const pid = pidOf(card.id)
    const group = groups.get(pid) ?? { pid, name: card.name, cards: [] }
    group.cards.push(card)
    groups.set(pid, group)
  }
  return [...groups.values()].sort((a, b) => a.name.localeCompare(b.name, 'ko'))
}

/**
 * 이미지 파일명에서 선수 찾기 — p{spid}.png, p{spid}_25.png, p{pid}.png 등.
 * 9자리 이상이면 spid(카드 자동 선택), 그보다 짧으면 pid(선수 검색만).
 */
export function parseFaceFileName(fileName: string): { pid: number; spid: number | null } | null {
  const match = /^p(\d+)/i.exec(fileName)
  if (!match) return null
  const id = Number(match[1])
  return match[1].length > 6 ? { pid: pidOf(id), spid: id } : { pid: id, spid: null }
}
