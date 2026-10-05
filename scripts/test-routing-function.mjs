import { access, readFile, readdir } from 'node:fs/promises'
import { extname, relative, resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'
import vm from 'node:vm'

const functionPath = fileURLToPath(new URL('./cloudfront-routing-function.js', import.meta.url))
const functionSource = await readFile(functionPath, 'utf8')
const handler = vm.runInNewContext(`${functionSource}\nhandler`, {})
const projectRoot = resolve(fileURLToPath(new URL('..', import.meta.url)))
const outputDirectory = resolve(projectRoot, 'out')

const cases = [
  ['/', '/index.html'],
  ['/catalogue', '/catalogue.html'],
  ['/catalogue/', '/catalogue.html'],
  ['/admin', '/admin.html'],
  ['/admin/dashboard', '/admin/dashboard.html'],
  ['/products/amul-unsalted-butter', '/products/_shell.html'],
  ['/products/amul-unsalted-butter/', '/products/_shell.html'],
  ['/products/', '/products.html'],
  ['/catalogue//', '/catalogue.html'],
  ['/products/Amul-Butter', '/products/_shell.html'],
  ['/products/does-not-exist', '/products/_shell.html'],
  ['/products/_shell.html', '/products/_shell.html'],
  ['/products/photo.png', '/products/photo.png'],
  ['/products/a/b', '/products/a/b.html'],
  ['/products', '/products.html'],
  ['/_next/static/chunks/a.js', '/_next/static/chunks/a.js'],
  ['/data/catalog-index.json', '/data/catalog-index.json'],
  ['/media/products/a/main-v1.webp', '/media/products/a/main-v1.webp'],
  ['/favicon.ico', '/favicon.ico'],
]

let failures = 0
for (const [input, expected] of cases) {
  const event = { request: { uri: input, querystring: { search: { value: 'butter' } } } }
  const actual = handler(event).uri
  if (actual === expected) {
    console.log(`PASS ${input} -> ${actual}`)
  } else {
    failures += 1
    console.error(`FAIL ${input}: expected ${expected}, got ${actual}`)
  }
}

async function findHtmlFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true })
  const files = []

  for (const entry of entries) {
    const entryPath = resolve(directory, entry.name)
    if (entry.isDirectory()) {
      files.push(...await findHtmlFiles(entryPath))
    } else if (entry.isFile() && extname(entry.name).toLowerCase() === '.html') {
      files.push(entryPath)
    }
  }

  return files
}

function cleanUrlForHtmlFile(filePath) {
  const relativePath = relative(outputDirectory, filePath).split(sep).join('/')
  if (relativePath === 'index.html') return '/'
  if (relativePath === '404.html') return '/404.html'
  if (relativePath.endsWith('/index.html')) {
    return `/${relativePath.slice(0, -'index.html'.length)}`
  }
  return `/${relativePath.slice(0, -'.html'.length)}`
}

async function checkBuildPages() {
  let htmlFiles
  try {
    htmlFiles = await findHtmlFiles(outputDirectory)
  } catch (error) {
    failures += 1
    console.error(`FAIL cannot inspect out/: ${error.message}`)
    return
  }

  for (const filePath of htmlFiles) {
    const cleanUrl = cleanUrlForHtmlFile(filePath)
    const rewrittenUri = handler({ request: { uri: cleanUrl, querystring: {} } }).uri
    const objectPath = resolve(outputDirectory, `.${rewrittenUri}`)
    const insideOutput = objectPath === outputDirectory || objectPath.startsWith(`${outputDirectory}${sep}`)

    try {
      if (!insideOutput) throw new Error('rewritten path escapes out/')
      await access(objectPath)
      console.log(`PASS build page ${cleanUrl} -> ${rewrittenUri}`)
    } catch (error) {
      failures += 1
      console.error(`FAIL build page ${cleanUrl} -> ${rewrittenUri}: ${error.message}`)
    }
  }

  try {
    await access(resolve(outputDirectory, '404.html'))
    console.log('PASS custom error page out/404.html exists')
  } catch {
    failures += 1
    console.error('FAIL out/404.html is missing; add an app/not-found.js page and rebuild the static export.')
  }
}

await checkBuildPages()

if (failures > 0) {
  console.error(`${failures} routing case(s) failed.`)
  process.exitCode = 1
} else {
  console.log(`All ${cases.length} routing cases passed.`)
}
