export const REQUEST_TIMEOUT_MS = 15_000
export const REQUEST_TIMEOUT_MESSAGE = 'The request timed out. Please try again.'

export async function fetchWithTimeout(
  input,
  options = {},
  {
    timeoutMs = REQUEST_TIMEOUT_MS,
    fetchImpl = globalThis.fetch,
  } = {},
) {
  const controller = new AbortController()
  const callerSignal = options.signal
  let timedOut = false
  let timeoutId

  const clearTimeoutTimer = () => {
    if (timeoutId !== undefined) {
      clearTimeout(timeoutId)
      timeoutId = undefined
    }
  }

  const abortFromCaller = () => {
    clearTimeoutTimer()
    controller.abort(callerSignal.reason)
  }

  if (callerSignal?.aborted) {
    controller.abort(callerSignal.reason)
  } else {
    timeoutId = setTimeout(() => {
      timedOut = true
      controller.abort()
    }, timeoutMs)
    callerSignal?.addEventListener('abort', abortFromCaller, { once: true })
  }

  try {
    return await fetchImpl(input, { ...options, signal: controller.signal })
  } catch (error) {
    if (timedOut) {
      throw new Error(REQUEST_TIMEOUT_MESSAGE)
    }
    throw error
  } finally {
    clearTimeoutTimer()
    callerSignal?.removeEventListener('abort', abortFromCaller)
  }
}
