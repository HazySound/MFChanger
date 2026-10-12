// 카드별 교체·바둑판 모드가 함께 쓰는 미페 교체 동작

import { markChanged } from '../../lib/app.svelte'
import { py } from '../../lib/bridge'
import { seasonIdOf, seasonOf } from '../../lib/meta.svelte'
import { confirm, toast, toastError } from '../../lib/notify.svelte'
import type { ImageInfo, ReplaceResult } from '../../lib/types'

/** 교체 동작 단계 — idle 외에는 다른 동작을 받지 않는다 (확인 창이 떠 있는 동안 포함) */
export type Phase = 'idle' | 'confirm' | 'apply' | 'restore'

const NOT_FOUND = 'players/not_found.png'
const SEASON_LIST_LIMIT = 12

function seasonNames(spids: number[]): string {
  const names = spids.map((spid) => seasonOf(spid)?.shortName ?? String(seasonIdOf(spid)))
  const shown = names.slice(0, SEASON_LIST_LIMIT).join(', ')
  return names.length > SEASON_LIST_LIMIT ? `${shown} 외 ${names.length - SEASON_LIST_LIMIT}장` : shown
}

/**
 * 교체 전 확인. 여러 카드가 같이 쓰는 파일이면 함께 바뀌는 카드를 알려주고,
 * 기본 이미지(not_found)는 교체를 막는다. 진행해도 되면 true.
 */
export async function confirmReplace(
  playerName: string,
  relative: string,
  sharedSpids: number[],
  verified = true,
): Promise<boolean> {
  if (relative === NOT_FOUND) {
    toast(
      '이 카드는 게임에서 기본 이미지(not_found)를 쓰고 있어 교체할 수 없습니다.\n교체하면 미페가 없는 모든 선수의 이미지가 바뀝니다.',
      'error',
    )
    return false
  }
  if (!verified) {
    return confirm(
      '게임 파일을 확인하지 못했습니다',
      `데이터센터에서 이 카드가 쓰는 미페 파일을 확인하지 못해 추정 경로(${relative})에 적용합니다.\n인게임에 반영되지 않을 수 있습니다. 계속할까요?`,
      { confirmLabel: '그래도 교체' },
    )
  }
  if (sharedSpids.length > 1) {
    return confirm(
      `카드 ${sharedSpids.length}장이 함께 바뀝니다`,
      `'${playerName}'의 카드 ${sharedSpids.length}장이 같은 미페 파일(${relative})을 씁니다.\n\n` +
        `함께 바뀌는 카드: ${seasonNames(sharedSpids)}\n\n카드별로 따로 바꿀 수 없습니다. 계속할까요?`,
      { confirmLabel: '모두 교체' },
    )
  }
  return true
}

/** 교체 실행 — 성공하면 알리고 다른 탭에 변경을 알린다. 실패하면 null. */
export async function replaceFace(
  spid: number,
  playerName: string,
  image: ImageInfo,
  relative: string,
): Promise<ReplaceResult | null> {
  try {
    const result = await (await py()).face.replace(spid, playerName, image.path, relative)
    toast('미페를 교체했습니다.')
    markChanged()
    return result
  } catch (error) {
    toastError(error)
    return null
  }
}

/** 확인 후 CDN의 공식 미페로 되돌린다. 실패·취소 시 null. */
export async function restoreOfficialFace(
  spid: number,
  playerName: string,
  relative: string,
): Promise<ReplaceResult | null> {
  const ok = await confirm(
    '공식 미페로 복원',
    `'${playerName}'의 미페를 공식 이미지로 되돌릴까요?\n넥슨 서버에서 공식 미페를 받아 덮어씁니다.`,
    { confirmLabel: '복원' },
  )
  if (!ok) return null
  try {
    const result = await (await py()).face.restore_official(spid, playerName, relative)
    toast('공식 미페로 복원했습니다.')
    markChanged()
    return result
  } catch (error) {
    toastError(error)
    return null
  }
}
