// 화면 전역 알림 — 토스트와 확인 대화상자

import { errorMessage } from './bridge'

export type Tone = 'success' | 'error' | 'info'

export interface Toast {
  id: number
  tone: Tone
  text: string
}

export interface ConfirmRequest {
  title: string
  message: string
  confirmLabel: string
  danger: boolean
  resolve: (ok: boolean) => void
}

const TOAST_MS = { success: 2800, info: 3600, error: 6000 }

export const notice = $state({
  toasts: [] as Toast[],
  confirm: null as ConfirmRequest | null,
})

let nextId = 1

export function toast(text: string, tone: Tone = 'success') {
  const id = nextId++
  notice.toasts.push({ id, tone, text })
  setTimeout(() => dismiss(id), TOAST_MS[tone])
}

export function toastError(error: unknown) {
  toast(errorMessage(error), 'error')
}

export function dismiss(id: number) {
  notice.toasts = notice.toasts.filter((t) => t.id !== id)
}

export function confirm(
  title: string,
  message: string,
  { confirmLabel = '확인', danger = false } = {},
): Promise<boolean> {
  // 이미 떠 있는 확인 창은 취소로 정리 (그 창을 기다리던 동작이 멈추지 않게)
  notice.confirm?.resolve(false)
  return new Promise((resolve) => {
    notice.confirm = {
      title,
      message,
      confirmLabel,
      danger,
      resolve: (ok) => {
        notice.confirm = null
        resolve(ok)
      },
    }
  })
}
