// The gateway `error` event (tui_gateway/prompt_turn.py) carries only a
// message — no error_surface. The dispatcher must still classify the two
// refusals it can mean so the card and toast read like a classified turn:
// plain words up front, raw text demoted to the detail line, and Retry gone
// where retrying reproduces the failure.
import { afterEach, describe, expect, it, vi } from 'vitest'

import { $notifications } from '@/store/notifications'

import { handleStatusEvent } from './status'
import type { GatewayEventContext } from './types'

vi.mock('@/store/native-notifications', () => ({ dispatchNativeNotification: vi.fn() }))
vi.mock('@/store/onboarding', () => ({ requestDesktopOnboarding: vi.fn() }))

const OWNED_REFUSAL =
  'Session 20260909_095312_6b93f5 already has a live owner (tui, pid 32977, lease age 22m). ' +
  'Attach through a compatible owner, or close the session in its owning surface before resuming here.'

function errorContext(message: string) {
  const failAssistantMessage = vi.fn()
  const payload = { message } as GatewayEventContext['payload']

  const ctx: GatewayEventContext = {
    deps: {
      compactedTurnRef: { current: new Set<string>() },
      failAssistantMessage,
      flushQueuedDeltas: vi.fn(),
      hydrateFromStoredSession: vi.fn(),
      queryClient: { invalidateQueries: vi.fn() },
      sessionStateByRuntimeIdRef: { current: new Map() },
      updateSessionState: vi.fn()
    } as unknown as GatewayEventContext['deps'],
    event: { payload, session_id: 'sess-1', type: 'error' },
    explicitSid: 'sess-1',
    fromActiveSource: () => true,
    isActiveEvent: false,
    occurredAt: 1_700_000_100,
    payload,
    scheduleConfigRefresh: vi.fn(),
    sessionId: 'sess-1'
  }

  return { ctx, failAssistantMessage }
}

afterEach(() => {
  $notifications.set([])
})

describe('gateway `error` event → error card + toast', () => {
  it('stamps SESSION_NOT_OWNED on a live-owner refusal so the card drops Retry', () => {
    const { ctx, failAssistantMessage } = errorContext(OWNED_REFUSAL)

    expect(handleStatusEvent(ctx)).toBe(true)

    expect(failAssistantMessage).toHaveBeenCalledWith(
      'sess-1',
      OWNED_REFUSAL,
      1_700_000_100,
      expect.objectContaining({ code: 'SESSION_NOT_OWNED', retryable: false })
    )
  })

  it('toasts the plain explanation, not the lease jargon, and keeps the raw text as detail', () => {
    const { ctx } = errorContext(OWNED_REFUSAL)

    handleStatusEvent(ctx)

    const toast = $notifications.get()[0]

    expect(toast.title).toBe("Hermes couldn't finish the reply")
    expect(toast.message).toMatch(/open in another Hermes window or terminal/)
    expect(toast.message).not.toMatch(/lease|pid|live owner/i)
    expect(toast.detail).toBe(OWNED_REFUSAL)
    expect(toast.action).toBeUndefined()
  })

  it('leaves an unclassified gateway error without a descriptor (card falls back to the generic copy)', () => {
    const { ctx, failAssistantMessage } = errorContext('HTTP 503: upstream connect error')

    handleStatusEvent(ctx)

    expect(failAssistantMessage).toHaveBeenCalledWith('sess-1', 'HTTP 503: upstream connect error', 1_700_000_100, null)
    expect($notifications.get()[0].message).toMatch(/Hermes couldn't finish this reply/)
  })
})
