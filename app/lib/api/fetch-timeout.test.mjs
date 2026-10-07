import assert from 'node:assert/strict'
import test from 'node:test'

import {
  fetchWithTimeout,
  REQUEST_TIMEOUT_MESSAGE,
  REQUEST_TIMEOUT_MS,
} from './fetch-timeout.mjs'

test('default timeout is 15 seconds', () => {
  assert.equal(REQUEST_TIMEOUT_MS, 15000)
})

function abortError() {
  return new DOMException('The operation was aborted.', 'AbortError')
}

test('aborts a stalled fetch at the timeout and reports the timeout message', async () => {
  let observedSignal
  const fetchImpl = (_input, { signal }) => new Promise((_resolve, reject) => {
    observedSignal = signal
    signal.addEventListener('abort', () => reject(abortError()), { once: true })
  })

  await assert.rejects(
    fetchWithTimeout('/slow', {}, { timeoutMs: 10, fetchImpl }),
    { message: REQUEST_TIMEOUT_MESSAGE },
  )
  assert.equal(observedSignal.aborted, true)
})

test('caller abort is propagated and is not reported as a timeout', async () => {
  const caller = new AbortController()
  const fetchImpl = (_input, { signal }) => new Promise((_resolve, reject) => {
    signal.addEventListener('abort', () => reject(abortError()), { once: true })
  })
  const request = fetchWithTimeout('/caller-abort', { signal: caller.signal }, {
    timeoutMs: 100,
    fetchImpl,
  })

  caller.abort()
  await assert.rejects(request, (error) => {
    assert.equal(error.name, 'AbortError')
    assert.notEqual(error.message, REQUEST_TIMEOUT_MESSAGE)
    return true
  })
})

test('successful fetch clears its timeout timer', async () => {
  const started = Date.now()
  const response = { ok: true }
  let observedSignal
  const actual = await fetchWithTimeout('/fast', {}, {
    timeoutMs: 20,
    fetchImpl: async (_input, { signal }) => {
      observedSignal = signal
      return response
    },
  })

  await new Promise((resolve) => setTimeout(resolve, 35))
  assert.equal(actual, response)
  assert.ok(Date.now() - started >= 20)
  assert.equal(observedSignal.aborted, false)
})
