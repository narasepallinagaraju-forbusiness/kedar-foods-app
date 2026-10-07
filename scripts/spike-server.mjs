import { createReadStream } from 'node:fs'
import { stat } from 'node:fs/promises'
import { createServer } from 'node:http'
import { extname, resolve, sep } from 'node:path'
import { Readable } from 'node:stream'
import { fileURLToPath } from 'node:url'

const projectRoot = resolve(fileURLToPath(new URL('..', import.meta.url)))
const outputRoot = resolve(projectRoot, 'out')
const port = Number(process.env.PORT || 3000)
const excludedPrefixes = ['/_next/', '/data/', '/media/']

const contentTypes = {
  '.css': 'text/css; charset=utf-8',
  '.html': 'text/html; charset=utf-8',
  '.ico': 'image/x-icon',
  '.jpeg': 'image/jpeg',
  '.jpg': 'image/jpeg',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.map': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.svg': 'image/svg+xml',
  '.txt': 'text/plain; charset=utf-8',
  '.wasm': 'application/wasm',
  '.webp': 'image/webp',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
}

function sendText(response, status, text) {
  response.writeHead(status, {
    'Content-Type': 'text/plain; charset=utf-8',
    'Cache-Control': 'no-store',
  })
  response.end(text)
}

function getCloudFrontOrigin() {
  const configuredOrigin = process.env.CLOUDFRONT_SITE_ORIGIN?.trim()
  if (!configuredOrigin) {
    throw new Error('Set CLOUDFRONT_SITE_ORIGIN to the deployed CloudFront site origin.')
  }

  let origin
  try {
    origin = new URL(configuredOrigin)
  } catch {
    throw new Error('CLOUDFRONT_SITE_ORIGIN must be a valid HTTPS origin.')
  }

  if (
    origin.protocol !== 'https:' ||
    origin.username ||
    origin.password ||
    origin.pathname !== '/' ||
    origin.search ||
    origin.hash
  ) {
    throw new Error('CLOUDFRONT_SITE_ORIGIN must be a valid HTTPS origin.')
  }

  return origin.origin
}

async function proxyCloudFrontAsset(response, pathname, search, method) {
  const origin = getCloudFrontOrigin()
  const upstream = await fetch(new URL(`${pathname}${search}`, `${origin}/`), { method })
  const headers = {}

  for (const header of ['content-type', 'cache-control', 'etag', 'last-modified', 'expires']) {
    const value = upstream.headers.get(header)
    if (value) headers[header] = value
  }

  response.writeHead(upstream.status, headers)
  if (method === 'HEAD' || !upstream.body) {
    response.end()
    return
  }

  Readable.fromWeb(upstream.body).pipe(response)
}

function shouldRewriteToProductShell(pathname) {
  let decodedPath
  try {
    decodedPath = decodeURIComponent(pathname)
  } catch {
    return false
  }

  if (excludedPrefixes.some((prefix) => decodedPath.startsWith(prefix))) return false
  if (extname(decodedPath)) return false
  return /^\/products\/[^/]+$/.test(decodedPath)
}

async function serveStaticFile(response, pathname, method) {
  let decodedPath
  try {
    decodedPath = decodeURIComponent(pathname)
  } catch {
    sendText(response, 400, 'Bad request')
    return
  }

  const requestedPath = decodedPath === '/'
    ? resolve(outputRoot, 'index.html')
    : resolve(outputRoot, `.${decodedPath}`)
  const insideOutput = requestedPath === outputRoot || requestedPath.startsWith(`${outputRoot}${sep}`)
  if (!insideOutput) {
    sendText(response, 403, 'Forbidden')
    return
  }

  const candidates = []
  if (decodedPath === '/') {
    candidates.push(requestedPath)
  } else if (!extname(decodedPath)) {
    candidates.push(`${requestedPath}.html`, resolve(requestedPath, 'index.html'))
  } else {
    candidates.push(requestedPath)
  }

  let filePath
  for (const candidate of candidates) {
    try {
      if ((await stat(candidate)).isFile()) {
        filePath = candidate
        break
      }
    } catch (error) {
      if (error.code !== 'ENOENT' && error.code !== 'ENOTDIR') throw error
    }
  }

  if (!filePath) {
    sendText(response, 404, 'Not found')
    return
  }

  response.writeHead(200, {
    'Content-Type': contentTypes[extname(filePath).toLowerCase()] || 'application/octet-stream',
    'Cache-Control': 'no-store',
  })
  if (method === 'HEAD') {
    response.end()
    return
  }
  createReadStream(filePath).pipe(response)
}

if (!Number.isInteger(port) || port < 1 || port > 65535) {
  throw new Error(`Invalid PORT value: ${process.env.PORT}`)
}

const server = createServer(async (request, response) => {
  const method = request.method || 'GET'
  if (method !== 'GET' && method !== 'HEAD') {
    sendText(response, 405, 'Method not allowed')
    return
  }

  let pathname
  try {
    pathname = new URL(request.url, 'http://localhost').pathname
  } catch {
    sendText(response, 400, 'Bad request')
    return
  }

  if (/^\/(?:data|media)(?:\/|$)/.test(pathname)) {
    try {
      const url = new URL(request.url, 'http://localhost')
      await proxyCloudFrontAsset(response, pathname, url.search, method)
    } catch (error) {
      console.error('CloudFront asset proxy failed:', error)
      if (!response.headersSent) sendText(response, 502, 'CloudFront asset proxy failed')
      else response.destroy(error)
    }
    return
  }

  const staticPath = shouldRewriteToProductShell(pathname)
    ? '/products/_shell.html'
    : pathname

  try {
    await serveStaticFile(response, staticPath, method)
  } catch (error) {
    console.error('Static file request failed:', error)
    if (!response.headersSent) sendText(response, 500, 'Internal server error')
    else response.destroy(error)
  }
})

server.listen(port, () => {
  console.log(`Static export spike server: http://localhost:${port}`)
})
