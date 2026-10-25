import { expect, mock, test } from 'claude-code/testing'

const PANE = {
  plugin: 'ontology-observer',
  component: 'Pane',
  requestId: 'ontology',
  props: {
    title: 'Ontology',
    isFocused: false,
    bodyColumns: 60,
    placement: 'dock',
    scroll: { offset: 0, bodyRows: 30 },
    view: {},
  },
} as const

const STATE = [
  { ts: '2026-10-24T10:00:00-0500', mode: 'validate', exit: 0, domains: ['orders'], errors: 0, warnings: 2,
    problems: ['warn: orders.md: invariant without a gate: Every Item has a price.', 'warn: orders.md: invariant without a gate: Start is before end.'] },
  { ts: '2026-10-24T10:01:00-0500', mode: 'changed', exit: 0, tier: 'touched', files: [], domains: [], ontology_changed: false, skip: null, base: null, staged: false, message: '' },
  { ts: '2026-10-24T10:02:00-0500', mode: 'touched', exit: 0, tier: 'touched',
    files: [{ path: 'src/utils/totals.ts', tier: 'touched', signals: [], domains: ['orders'] }],
    domains: ['orders'], message: '' },
  { ts: '2026-10-24T10:03:00-0500', mode: 'touched', exit: 2, tier: 'affecting',
    files: [{ path: 'src/types/orders.ts', tier: 'affecting',
      signals: [{ kind: 'declaration', name: 'ItemRecord', entity: 'Item', change: 'changed' }], domains: ['orders'] }],
    domains: ['orders'], message: 'ontology: orders.ts changes what ontology/orders.md describes' },
]
const TEXT = STATE.map(r => JSON.stringify(r)).join('\n') + '\n'

type Body = Extract<Parameters<typeof test>[1], (...args: never[]) => unknown>

const ONTOLOGY = `---
domain: demo
governs:
  - "src/**"
declarations:
  - "Item: ItemRecord, Item"
  - "Order: OrderRecord"
---

# Demo

## Intent

Keep the well document honest.

## Entities

- **Item** — a product line. Key: \`id\`.
- **Order** — a customer purchase.

## Relationships

- \`(Order)-[CONTAINS]->(Item)\`  0..*
- \`(Item)-[SHIPPED_IN]->(Parcel)\`

## Invariants

Contents

- An Order is larger than any Item in it. [confirmed: reviewer 2026-10-24] [gate: \`itemPlacement.test.ts\`]
- Every Item has a price. (inferred)

Dates

- An Order has a date.
- A Item's \`weight\` is positive.

## Disagreements

- Order-to-item margin: 0.1 (\`validate.ts:MARGIN\`) against 2 (\`Canvas.tsx:AUTO_MARGIN\`); the Item form checks neither.
- An order may equal the order before it in size (\`clampSizeEdit\`) but the canvas requires it smaller.

## Vocabulary

- **Item** — any product line.

## Out of scope

- Billing.
`

const DIFF = '--- ItemRecord\n+++ ItemRecord\n@@ -2,3 +2,4 @@\n   id: string;\n   price: number;\n+  weight: number;\n }'

function engine(on: Parameters<Body>[1], status: string[], file: { text: string | null }, ontology: string | null = null, submitted: string[] = []) {
  mock.store(on)
  on('prompt.submit', (_, e) => {
    submitted.push(e.text)
    return { text: e.text }
  })
  on('command.register', () => ({ value: { command: 'ontology' } }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('ui.status', (_, e) => {
    status.push(String(e.text))
    return { value: undefined }
  })
  on('session.root', () => ({ value: '/repo' }))
  on('fs.exists', (_, e) => {
    expect(e.path).toBe('/repo/.claude/ontology-state.jsonl')
    return { value: file.text !== null }
  })
  on('fs.list', () => {
    if (ontology === null) throw new Error('ENOENT')
    return { value: [
      { name: 'README.md', kind: 'file', size: 1, mtimeMs: 0, isLink: false },
      { name: 'demo.md', kind: 'file', size: 1, mtimeMs: 0, isLink: false },
    ] }
  })
  on('fs.read', (_, e) => {
    if (e.path.endsWith('.md')) {
      if (ontology === null || e.path.endsWith('README.md')) throw new Error('ENOENT')
      return { value: ontology }
    }
    if (file.text === null) throw new Error('ENOENT')
    return { value: file.text }
  })
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('classic.PostToolUse', () => ({}))
  on('classic.Stop', () => ({}))
}

test('the pane shows each stage, this turn\'s files and the status line', async ($, on) => {
  const status: string[] = []
  engine(on, status, { text: TEXT })
  await $.session.start({ cwd: '/repo', surface: 'desktop', isInteractive: true })

  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ ...PANE, surface })
    expect((await ui.find({ type: 'Text', text: /^Ontology file/ }))?.text).toMatch(/well-formed, 2 warnings/)
    // each warning is an issue of its own, as a sentence
    expect((await ui.find({ type: 'Text', text: /Every Item has a price/ }))?.text).toMatch(/^No gate: /)
    expect(await ui.find({ type: 'Text', text: /Start is before end/ })).toBeDefined()
    expect((await ui.find({ type: 'Text', text: /^Last edit/ }))?.text).toMatch(/orders\.ts changed Item, ontology\/orders\.md not updated/)
    // the block is an issue too, said plainly, not the checker's message
    expect((await ui.find({ type: 'Text', text: /not updated for Item/ }))?.text).toMatch(/ItemRecord changed in .*orders\.ts/)
    expect(await ui.find({ type: 'Text', text: /changes what ontology/ })).toBeUndefined()
    expect((await ui.find({ type: 'Text', text: /^End of turn/ }))?.text).toMatch(/in step|ontology updated|no governed code/)
    expect((await ui.find({ type: 'Text', text: /^Last commit/ }))?.text).toMatch(/not run yet/)
    // this turn = touched records after the last stop record: both files, with tier and signal
    expect((await ui.find({ type: 'Text', text: /^totals\.ts/ }))?.text).toMatch(/nothing the ontology names changed/)
    expect((await ui.find({ type: 'Text', text: /^orders\.ts:/ }))?.text).toMatch(/ItemRecord changed, which describes Item/)
    await ui.unmount()
  }
  expect(status.at(-1)).toMatch(/ontology: blocked/)
  expect(status.at(-1)).toMatch(/orders\.ts/)
})

test('a settings hook run refreshes the pane and the status line', async ($, on) => {
  const status: string[] = []
  const file = { text: '' }
  engine(on, status, file)
  await $.session.start({ cwd: '/repo', surface: 'desktop', isInteractive: true })
  expect(status.at(-1)).toMatch(/no checks yet/)

  file.text = TEXT
  await $.classic.PostToolUse({ tool_name: 'Edit', tool_input: { file_path: 'x' }, tool_response: {}, tool_use_id: 't1' })
  expect(status.at(-1)).toMatch(/ontology: blocked/)
  const open = await $.ui.mount({ ...PANE, surface: 'terminal' })
  expect(await open.find({ type: 'Text', text: /not updated for Item/ })).toBeDefined()
  await open.unmount()

  file.text = TEXT + JSON.stringify({ ts: '2026-10-24T10:04:00-0500', mode: 'changed', exit: 0, tier: 'affecting',
    files: [], domains: ['orders'], ontology_changed: true, skip: null, base: null, staged: false, message: '' }) + '\n'
  await $.classic.Stop({ stop_hook_active: false })
  expect(status.at(-1)).toMatch(/ontology: passed/)
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /^End of turn/ }))?.text).toMatch(/ontology updated with the code/)
  // the ontology was updated: the block is resolved, not an open issue any more
  expect(await ui.find({ type: 'Text', text: /not updated for Item/ })).toBeUndefined()
  // nothing of it is listed; the Last edit line says it was resolved
  expect(await ui.find({ type: 'Text', text: /^RESOLVED/ })).toBeUndefined()
  expect((await ui.find({ type: 'Text', text: /^Last edit/ }))?.text).toMatch(/resolved at 10:04:00/)
  // the turn that just ended stays on screen until the next turn's first edit check
  expect(await ui.find({ type: 'Text', text: /totals\.ts/ })).toBeDefined()
  await ui.unmount()

  // a turn with no edits at all (a second stop check) does not clear it either
  file.text += JSON.stringify({ ts: '2026-10-24T10:04:30-0500', mode: 'changed', exit: 0, tier: 'none',
    files: [], domains: [], ontology_changed: false, skip: null, base: null, staged: false, message: '' }) + '\n'
  await $.classic.Stop({ stop_hook_active: false })
  const quiet = await $.ui.mount({ ...PANE, surface: 'terminal' })
  expect(await quiet.find({ type: 'Text', text: /totals\.ts/ })).toBeDefined()
  await quiet.unmount()

  file.text += JSON.stringify({ ts: '2026-10-24T10:05:00-0500', mode: 'touched', exit: 0, tier: 'touched',
    files: [{ path: 'src/next.ts', tier: 'touched', signals: [], domains: ['orders'] }], domains: ['orders'], message: '' }) + '\n'
  await $.classic.PostToolUse({ tool_name: 'Write', tool_input: { file_path: 'src/next.ts' }, tool_response: {}, tool_use_id: 't2' })
  const next = await $.ui.mount({ ...PANE, surface: 'terminal' })
  expect(await next.find({ type: 'Text', text: /next\.ts/ })).toBeDefined()
  expect(await next.find({ type: 'Text', text: /totals\.ts/ })).toBeUndefined()
  await next.unmount()
})

test('a missing state file leaves the pane empty, not broken', async ($, on) => {
  const status: string[] = []
  engine(on, status, { text: null })
  await $.session.start({ cwd: '/repo', surface: 'desktop', isInteractive: true })
  const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  expect((await ui.find({ type: 'Text', text: /no checks/ }))?.text).toMatch(/no checks yet/)
  await ui.unmount()
})

test('an affecting edit draws a card per entity: change, diff, chain and invariants', async ($, on) => {
  const status: string[] = []
  const rec = { ts: '2026-10-24T10:05:00-0500', mode: 'touched', exit: 2, tier: 'affecting',
    files: [{ path: 'src/types.ts', tier: 'affecting',
      signals: [{ kind: 'declaration', name: 'ItemRecord', entity: 'Item', change: 'changed', diff: DIFF }],
      domains: ['demo'] }],
    domains: ['demo'], message: 'ontology: src/types.ts changes what ontology/demo.md describes' }
  engine(on, status, { text: JSON.stringify(rec) + '\n' }, ONTOLOGY)
  await $.session.start({ cwd: '/repo', surface: 'desktop', isInteractive: true })

  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ ...PANE, surface })
    // the card names the entity, then its ontology description on its own line
    expect(await ui.find({ type: 'Text', text: /^Item$/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /^a product line/ })).toBeDefined()
    // what changed, in which declaration, as the changed lines alone; the full diff is behind a toggle
    expect((await ui.find({ type: 'Text', text: /ItemRecord changed in/ }))?.text).toMatch(/src\/types\.ts/)
    expect((await ui.find({ type: 'Text', text: /weight: number/ }))?.text).toMatch(/^\s*\+/)
    expect(await ui.find({ type: 'Code' })).toBeUndefined()
    // rules at risk: the one that names the changed field; the entity's other rules are folded
    expect(await ui.find({ type: 'Text', text: /weight.*is positive/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /^no gate$/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /larger than any Item/ })).toBeUndefined()
    expect(await ui.find({ type: 'Text', text: /An Order has a date/ })).toBeUndefined()
    // relationships: none names weight, so none is at risk; the chain is behind a toggle
    expect(await ui.find({ type: 'Text', text: /none at risk/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /CONTAINS/ })).toBeUndefined()
    await ui.unmount()
  }

  // the toggles unfold the rest: the entity's rules, every rule, every relationship, the full diff
  const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  const press = async (re: RegExp) => {
    const b = await ui.find({ type: 'Button', text: re })
    expect(b?.key).toBeDefined()
    await $.ui.press({ plugin: 'ontology-observer', key: b!.key!, requestId: 'ontology', surface: 'desktop' })
  }
  await press(/about Item \(3\)/)
  expect(await ui.find({ type: 'Text', text: /larger than any Item/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /^gate  itemPlacement\.test\.ts$/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /is positive.*\(at risk\)/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /An Order has a date/ })).toBeUndefined()
  await press(/all \(4\)/)
  expect(await ui.find({ type: 'Text', text: /An Order has a date/ })).toBeDefined()
  await press(/all \(2\)/)
  expect((await ui.find({ type: 'Text', text: /CONTAINS/ }))?.text).toMatch(/\(Order\)-\[CONTAINS\]->\(Item\)/)
  expect(await ui.find({ type: 'Text', text: /SHIPPED_IN/ })).toBeDefined()
  await press(/full diff/)
  const code = await ui.find({ type: 'Code' })
  expect(code?.props.source).toContain('+  weight: number;')
  expect(code?.props.format).toBe('diff')
  await ui.unmount()
})

test('without an ontology directory the card still names the entity and the change', async ($, on) => {
  const status: string[] = []
  const rec = { ts: '2026-10-24T10:05:00-0500', mode: 'touched', exit: 2, tier: 'affecting',
    files: [{ path: 'src/types.ts', tier: 'affecting',
      signals: [{ kind: 'declaration', name: 'Item', entity: 'Item', change: 'added' }], domains: ['demo'] }],
    domains: ['demo'], message: '' }
  engine(on, status, { text: JSON.stringify(rec) + '\n' })
  await $.session.start({ cwd: '/repo', surface: 'desktop', isInteractive: true })
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /^Item$/ }))?.text).toBe('Item')
  expect((await ui.find({ type: 'Text', text: /Item added in/ }))?.text).toMatch(/src\/types\.ts/)
  await ui.unmount()
})

test('each issue is a bordered box with fix, explore and leave actions', async ($, on) => {
  const status: string[] = []
  const submitted: string[] = []
  const lines = [
    { ts: '2026-10-24T10:00:00-0500', mode: 'validate', exit: 0, domains: ['demo'], errors: 0, warnings: 1,
      problems: ['warn: demo.md: invariant without a gate: Every Item has a price.'] },
    { ts: '2026-10-24T10:05:00-0500', mode: 'touched', exit: 2, tier: 'affecting',
      files: [{ path: 'src/types.ts', tier: 'affecting',
        signals: [{ kind: 'declaration', name: 'ItemRecord', entity: 'Item', change: 'changed', diff: DIFF }], domains: ['demo'] }],
      domains: ['demo'], message: 'ontology: src/types.ts changes what ontology/demo.md describes' },
  ]
  engine(on, status, { text: lines.map(l => JSON.stringify(l)).join('\n') + '\n' }, ONTOLOGY, submitted)
  on('turn.complete', (_, e) => ({ text: e.answer }))
  const turnEnds = () => $.turn.complete({ reason: 'answer', answer: 'done', durationMs: 1, isAborted: false, turnId: 't1' })
  await $.session.start({ cwd: '/repo', surface: 'desktop', isInteractive: true })

  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ ...PANE, surface })
    // the block comes first, as an error, with the rules the change puts at risk
    const block = await ui.find({ type: 'Text', text: /not updated for Item/ })
    expect(block?.text).toMatch(/ItemRecord changed in src\/types\.ts/)
    expect(await ui.find({ type: 'Text', text: /weight.*is positive/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /^no gate$/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /larger than any Item/ })).toBeUndefined()
    // then the gate warning
    expect((await ui.find({ type: 'Text', text: /No gate: Every Item has a price/ }))?.text).toBeDefined()
    // three actions on the first issue
    const fix = await ui.find({ type: 'Button', text: /Fix it/ })
    const look = await ui.find({ type: 'Button', text: /Explore issue/ })
    const leave = await ui.find({ type: 'Button', text: /Leave it/ })
    expect(fix?.key).toBeDefined()
    expect(look?.key).toBeDefined()
    expect(leave?.key).toBeDefined()
    await ui.unmount()
  }

  const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  const fix = await ui.find({ type: 'Button', text: /Fix it/ })
  await $.ui.press({ plugin: 'ontology-observer', key: fix!.key!, requestId: 'ontology', surface: 'desktop' })
  expect(submitted.at(-1)).toMatch(/ontology\/demo\.md/)
  expect(submitted.at(-1)).toMatch(/ItemRecord/)
  expect(submitted.at(-1)).toMatch(/It adds weight\./)
  await turnEnds() // the fix turn ran; the actions are back

  const look = await ui.find({ type: 'Button', text: /Explore issue/ })
  await $.ui.press({ plugin: 'ontology-observer', key: look!.key!, requestId: 'ontology', surface: 'desktop' })
  const explore = submitted.at(-1) ?? ''
  // a brainstorming chat, seeded with the rule, its gate, and the disagreement that names the entity
  expect(explore).toMatch(/brainstorm/i)
  expect(explore).toMatch(/without editing/i)
  expect(explore).toMatch(/larger than any Item.*itemPlacement\.test\.ts/)
  expect(explore).toMatch(/Every Item has a price.*no gate/)
  expect(explore).toMatch(/Order-to-item margin/)
  expect(explore).not.toMatch(/order before it in size/)
  await turnEnds()

  const leave = await ui.find({ type: 'Button', text: /Leave it/ })
  await $.ui.press({ plugin: 'ontology-observer', key: leave!.key!, requestId: 'ontology', surface: 'desktop' })
  await ui.unmount()

  // left alone: gone from the pane, counted, and still gone on a fresh draw
  const again = await $.ui.mount({ ...PANE, surface: 'desktop' })
  expect(await again.find({ type: 'Text', text: /not updated for Item/ })).toBeUndefined()
  expect(await again.find({ type: 'Text', text: /1 left alone/ })).toBeDefined()
  expect(await again.find({ type: 'Text', text: /^LEFT ALONE$/ })).toBeUndefined()
  // the gate warning is still there with its own actions
  expect(await again.find({ type: 'Text', text: /No gate: Every Item has a price/ })).toBeDefined()
  const fixGate = await again.find({ type: 'Button', text: /Fix it/ })
  await $.ui.press({ plugin: 'ontology-observer', key: fixGate!.key!, requestId: 'ontology', surface: 'desktop' })
  expect(submitted.at(-1)).toMatch(/gate/i)
  expect(submitted.at(-1)).toMatch(/Every Item has a price/)
  // Show lists it, dim, with a way back; Take it back reopens it with its actions
  const show = await again.find({ type: 'Button', text: /^Show$/ })
  await $.ui.press({ plugin: 'ontology-observer', key: show!.key!, requestId: 'ontology', surface: 'desktop' })
  expect(await again.find({ type: 'Text', text: /^LEFT ALONE$/ })).toBeDefined()
  const back = await again.find({ type: 'Button', text: /Take it back/ })
  await $.ui.press({ plugin: 'ontology-observer', key: back!.key!, requestId: 'ontology', surface: 'desktop' })
  expect(await again.find({ type: 'Text', text: /not updated for Item/ })).toBeDefined()
  expect(await again.find({ type: 'Text', text: /left alone/ })).toBeUndefined()
  await again.unmount()
})

test('a pressed action shows in the box until the turn it started ends', async ($, on) => {
  const status: string[] = []
  const submitted: string[] = []
  const lines = [
    { ts: '2026-10-24T10:00:00-0500', mode: 'validate', exit: 0, domains: ['demo'], errors: 0, warnings: 1,
      problems: ['warn: demo.md: invariant without a gate: Every Item has a price.'] },
  ]
  engine(on, status, { text: lines.map(l => JSON.stringify(l)).join('\n') + '\n' }, ONTOLOGY, submitted)
  on('turn.complete', (_, e) => ({ text: e.answer }))
  await $.session.start({ cwd: '/repo', surface: 'desktop', isInteractive: true })

  const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  const fix = await ui.find({ type: 'Button', text: /Fix it/ })
  await $.ui.press({ plugin: 'ontology-observer', key: fix!.key!, requestId: 'ontology', surface: 'desktop' })
  // the box says what is happening, and its actions are gone while it does
  expect((await ui.find({ type: 'Text', text: /Fixing in chat/ }))?.text).toMatch(/Fixing in chat/)
  expect(await ui.find({ type: 'Button', text: /Fix it/ })).toBeUndefined()
  expect(await ui.find({ type: 'Button', text: /Explore issue/ })).toBeUndefined()
  await ui.unmount()

  // the turn the prompt started ends: the actions come back
  await $.turn.complete({ reason: 'answer', answer: 'done', durationMs: 1, isAborted: false, turnId: 't1' })
  const after = await $.ui.mount({ ...PANE, surface: 'desktop' })
  expect(await after.find({ type: 'Text', text: /Fixing in chat/ })).toBeUndefined()
  expect(await after.find({ type: 'Button', text: /Fix it/ })).toBeDefined()
  await after.unmount()
})


test('every rule is on the pane, grouped as the file groups them, unfolding on request', async ($, on) => {
  const status: string[] = []
  engine(on, status, { text: '' }, ONTOLOGY)
  await $.session.start({ cwd: '/repo', surface: 'desktop', isInteractive: true })
  const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  expect((await ui.find({ type: 'Text', text: /4 in ontology\/demo\.md/ }))?.text).toMatch(/3 without a gate/)
  const contents = await ui.find({ type: 'Button', text: /Contents \(2\)/ })
  expect(contents?.text).toMatch(/^▸/)
  expect(await ui.find({ type: 'Button', text: /Dates \(2\)/ })).toBeDefined()
  // folded: no rule text on the pane
  expect(await ui.find({ type: 'Text', text: /larger than any Item/ })).toBeUndefined()
  await $.ui.press({ plugin: 'ontology-observer', key: contents!.key!, requestId: 'ontology', surface: 'desktop' })
  expect((await ui.find({ type: 'Button', text: /Contents \(2\)/ }))?.text).toMatch(/^▾/)
  expect(await ui.find({ type: 'Text', text: /larger than any Item/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /^gate  itemPlacement/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /Every Item has a price/ })).toBeDefined()
  // the file's status markers are bookkeeping, not part of the rule
  expect(await ui.find({ type: 'Text', text: /confirmed:|\(inferred\)/ })).toBeUndefined()
  expect(await ui.find({ type: 'Text', text: /An Order has a date/ })).toBeUndefined()
  await ui.unmount()
})

test('a change reruns the tests of the rules it touches: pass is CLEAN, fail is ERROR with the output, unrun is WARNING', async ($, on) => {
  const status: string[] = []
  const rec = { ts: '2026-10-24T11:40:00-0500', mode: 'changed', exit: 2, staged: true, files: [], domains: ['demo'],
    changed_functions: { 'src/fit.ts': ['findItemsLargerThanOrder'] },
    rules: [
      { id: 'an-order-is-larger', text: 'An Order is larger than any Item in it.', domain: 'demo', status: 'fail',
        tests: ['orderItemFit.test.ts'], hit: [{ file: 'src/fit.ts', name: 'findItemsLargerThanOrder' }],
        runs: [{ test: 'orderItemFit.test.ts', status: 'fail', output: 'AssertionError: expected [] to have length 1' }] },
      { id: 'every-item-has-a-price', text: 'Every Item has a price.', domain: 'demo', status: 'pass',
        tests: ['itemPrice.test.ts'], hit: [{ file: 'src/fit.ts', name: 'findItemsLargerThanOrder' }],
        runs: [{ test: 'itemPrice.test.ts', status: 'pass' }] },
      { id: 'an-order-has-a-date', text: 'An Order has a date.', domain: 'demo', status: 'unrun',
        tests: ['orderDate.test.ts'], hit: [{ file: 'src/fit.ts', name: 'findItemsLargerThanOrder' }], runs: [] },
    ],
    message: "A rule's test fails after this change: An Order is larger than any Item in it." }
  engine(on, status, { text: JSON.stringify(rec) + '\n' }, ONTOLOGY)
  await $.session.start({ cwd: '/repo', surface: 'desktop', isInteractive: true })
  const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  // the failing rule is an ERROR issue: the sentence, the test, the function that linked it, and the test's output
  expect((await ui.find({ type: 'Text', text: /fails after this change/ }))?.text).toMatch(/An Order is larger than any Item in it/)
  expect((await ui.find({ type: 'Text', text: /AssertionError: expected \[\] to have length 1/ }))).toBeDefined()
  expect((await ui.find({ type: 'Text', text: /orderItemFit\.test\.ts.*findItemsLargerThanOrder/ }))).toBeDefined()
  expect(await ui.find({ type: 'Button', text: /^Fix it$/ })).toBeDefined()
  // the rule whose test did not run is a WARNING
  expect((await ui.find({ type: 'Text', text: /did not run/ }))?.text).toMatch(/An Order has a date/)
  // the rule whose test passed is CLEAN: a tick line under a header that counts
  expect((await ui.find({ type: 'Text', text: /^RULES RUN/ }))).toBeDefined()
  expect((await ui.find({ type: 'Text', text: /1 of 3 pass/ }))).toBeDefined()
  expect((await ui.find({ type: 'Text', text: /^✓ Every Item has a price/ }))).toBeDefined()
  await ui.unmount()
})

test('an edit to a rule\'s gate file is an issue box naming the rule, with fix, explore and leave', async ($, on) => {
  const status: string[] = []
  const submitted: string[] = []
  const lines = [
    { ts: '2026-10-25T07:48:24-0500', mode: 'touched', exit: 2, tier: 'affecting',
      files: [{ path: 'src/fit.ts', tier: 'affecting',
        signals: [{ kind: 'gate-file', name: 'fit.ts', invariant: 'An Order is larger than any Item in it.' }], domains: ['demo'] }],
      domains: ['demo'], message: 'ontology: src/fit.ts changes what ontology/demo.md describes' },
  ]
  engine(on, status, { text: lines.map(l => JSON.stringify(l)).join('\n') + '\n' }, ONTOLOGY, submitted)
  on('turn.complete', (_, e) => ({ text: e.answer }))
  await $.session.start({ cwd: '/repo', surface: 'desktop', isInteractive: true })

  const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  const title = await ui.find({ type: 'Text', text: /fit\.ts enforces the rule/ })
  expect(title?.text).toMatch(/An Order is larger than any Item in it\./)
  expect(title?.text).toMatch(/ontology\/demo\.md was not updated/)
  expect(await ui.find({ type: 'Text', text: /^ERROR$/ })).toBeDefined()
  expect(await ui.find({ type: 'Button', text: /Explore issue/ })).toBeDefined()
  expect(await ui.find({ type: 'Button', text: /Leave it/ })).toBeDefined()

  const fix = await ui.find({ type: 'Button', text: /Fix it/ })
  await $.ui.press({ plugin: 'ontology-observer', key: fix!.key!, requestId: 'ontology', surface: 'desktop' })
  const fixText = submitted.at(-1) ?? ''
  expect(fixText).toMatch(/src\/fit\.ts/)
  expect(fixText).toMatch(/An Order is larger than any Item in it\./)
  expect(fixText).toMatch(/ontology\/demo\.md/)
  expect(fixText).toMatch(/ontology-skip:/)
  await $.turn.complete({ reason: 'answer', answer: 'done', durationMs: 1, isAborted: false, turnId: 't1' })

  const look = await ui.find({ type: 'Button', text: /Explore issue/ })
  await $.ui.press({ plugin: 'ontology-observer', key: look!.key!, requestId: 'ontology', surface: 'desktop' })
  const explore = submitted.at(-1) ?? ''
  expect(explore).toMatch(/larger than any Item.*itemPlacement\.test\.ts/)
  expect(explore).toMatch(/Order-to-item margin/)
  await ui.unmount()
})
