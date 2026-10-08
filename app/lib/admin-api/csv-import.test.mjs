import assert from 'node:assert/strict'
import test from 'node:test'
import { chunkRows, parseCsv, prepareImport } from './csv-import.mjs'

const CATEGORIES = ['Dairy', 'Chocolate']
const HEADER = 'sku,name,brand,category,businessType,quantities,description,isTrending,sortRank,status'

function run(...lines) {
  return prepareImport([HEADER, ...lines].join('\n'), { categories: CATEGORIES })
}

test('parseCsv handles quotes, commas, newlines in quotes, CRLF and BOM', () => {
  const rows = parseCsv('\uFEFFa,b\r\n"x, y","He said ""hi""\nthere"\r\n')
  assert.deepEqual(rows, [['a', 'b'], ['x, y', 'He said "hi"\nthere']])
})

test('parseCsv rejects an unclosed quote and skips blank lines', () => {
  assert.throws(() => parseCsv('a,b\n"oops,1'))
  assert.deepEqual(parseCsv('a\n\n\nb\n'), [['a'], ['b']])
})

test('a good row becomes a live payload with lists split on |', () => {
  const { rows } = run('kf-1,Cream,Amul,dairy,bakery|Cafe,1L|5L,Nice,yes,10,')
  assert.deepEqual(rows[0].errors, [])
  assert.deepEqual(rows[0].payload, {
    sku: 'KF-1',
    name: 'Cream',
    brand: 'Amul',
    category: 'Dairy',
    businessType: ['Bakery', 'Cafe'],
    quantities: ['1L', '5L'],
    description: 'Nice',
    isTrending: true,
    status: 'PUBLISHED',
    sortRank: 10,
  })
  assert.equal(rows[0].line, 2)
})

test('ARCHIVED is honoured and blank optional columns are fine', () => {
  const { rows } = run('KF-2,Cream,Amul,Dairy,Bakery,1L,,,,archived')
  assert.deepEqual(rows[0].errors, [])
  assert.equal(rows[0].status, 'ARCHIVED')
  assert.equal('sortRank' in rows[0].payload, false)
})

test('bad values are reported per row', () => {
  const { rows } = run(
    'KF-3,Cream,Amul,Nope,Bakery,1L,,,,',
    'KF-4,Cream,Amul,Dairy,Shop,1L,,,,',
    'KF-5,Cream,Amul,Dairy,Bakery,1L,,maybe,,',
    'KF-6,Cream,Amul,Dairy,Bakery,1L,,,abc,',
    'KF-7,Cream,Amul,Dairy,Bakery,1L,,,,LIVE',
    'bad sku,Cream,Amul,Dairy,Bakery,1L,,,,',
    'KF-8,Cream,Amul,Dairy,Bakery,,,,,',
  )
  assert.equal(rows.length, 7)
  for (const row of rows) assert.ok(row.errors.length > 0, row.sku)
})

test('a SKU repeated inside the file is flagged on the second line only', () => {
  const { rows } = run(
    'KF-9,Cream,Amul,Dairy,Bakery,1L,,,,',
    'kf-9,Cream,Amul,Dairy,Bakery,1L,,,,',
  )
  assert.deepEqual(rows[0].errors, [])
  assert.match(rows[1].errors[0], /repeated/)
})

test('file level problems', () => {
  assert.match(prepareImport('', { categories: CATEGORIES }).fileError, /empty/)
  assert.match(prepareImport(HEADER, { categories: CATEGORIES }).fileError, /no products/)
  assert.match(prepareImport('sku,name\nA,B', { categories: CATEGORIES }).fileError, /Missing/)
  assert.match(
    prepareImport(`${HEADER},extra\n`, { categories: CATEGORIES }).fileError,
    /Unknown column/,
  )
  const many = Array.from(
    { length: 501 },
    (_, i) => `KF-${i + 10},Cream,Amul,Dairy,Bakery,1L,,,,`,
  )
  assert.match(run(...many).fileError, /limit is 500/)
  assert.match(
    prepareImport('x'.repeat(1024 * 1024 + 1), { categories: CATEGORIES }).fileError,
    /1 MB/,
  )
})

test('chunkRows splits into batches of the given size', () => {
  const chunks = chunkRows([1, 2, 3, 4, 5], 2)
  assert.deepEqual(chunks, [[1, 2], [3, 4], [5]])
})
