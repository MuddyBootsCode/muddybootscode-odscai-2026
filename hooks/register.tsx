import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { Domain, Invariant, Pressed, Relationship, Signal, StateFile, StateRecord, View, RuleRun } from '../types'

const PANE = 'ontology'
const STATE = '.claude/ontology-state.jsonl'
const ONTOLOGY_DIR = 'ontology'
const EDIT_TOOLS = new Set(['Edit', 'Write', 'MultiEdit'])
const records = atom({ plugin: 'ontology-observer', key: 'records' } as const, [])
const ontology = atom({ plugin: 'ontology-observer', key: 'ontology' } as const, [])
const left = atom({ plugin: 'ontology-observer', key: 'left' } as const, [])
const pressed = atom({ plugin: 'ontology-observer', key: 'pressed' } as const, {})
const view = atom({ plugin: 'ontology-observer', key: 'view' } as const, {})
const DEFAULT_VIEW: View = { rules: 'risk', relationships: false, diff: false }
const showLeft = atom({ plugin: 'ontology-observer', key: 'showLeft' } as const, false)
const openGroups = atom({ plugin: 'ontology-observer', key: 'openGroups' } as const, [])
const LEFT_KEY = 'left'

// ---------- the state record ----------

// One lifecycle stage per way the checker is run; a record's mode and flags pick it.
type Stage = 'validate' | 'edit' | 'stop' | 'commit' | 'ci'
const STAGES: Stage[] = ['validate', 'edit', 'stop', 'commit', 'ci']

function stageOf(r: StateRecord): Stage | undefined {
  if (r.mode === 'validate') return 'validate'
  if (r.mode === 'touched') return 'edit'
  if (r.mode === 'changed') return r.base ? 'ci' : r.staged ? 'commit' : 'stop'
  return undefined
}

function parseState(text: string): StateRecord[] {
  const out: StateRecord[] = []
  for (const line of text.split('\n')) {
    if (!line.trim()) continue
    try {
      const r = JSON.parse(line)
      if (r && typeof r.mode === 'string') out.push(r)
    } catch {
      // a half-written line is skipped, never fatal
    }
  }
  return out
}

function clock(ts: string): string {
  const m = /T(\d\d:\d\d:\d\d)/.exec(ts)
  return m?.[1] ?? ts
}

function base(path: string): string {
  return path.slice(path.lastIndexOf('/') + 1)
}

function verdict(r: StateRecord): string {
  if (r.skip) return `skipped (${r.skip})`
  if (r.exit === 0) return 'passed'
  return 'blocked'
}

function detail(r: StateRecord): string {
  if (r.mode === 'validate') {
    const w = r.warnings ?? 0
    const e = r.errors ?? 0
    return e ? `${e} errors` : w ? `${w} warnings` : 'clean'
  }
  const files = r.files ?? []
  const affecting = files.filter(f => f.tier === 'affecting')
  if (affecting.length) return `affecting ${affecting.map(f => base(f.path)).join(', ')}`
  const [one] = files
  if (one) return `touched ${files.length === 1 ? base(one.path) : `${files.length} files`}`
  return r.mode === 'changed' && r.ontology_changed ? 'ontology updated' : 'nothing governed'
}

function signalText(s: Signal): string {
  if (s.kind === 'declaration') return `${s.name} ${s.change ?? 'changed'}, which describes ${s.entity}`
  if (s.kind === 'parity') return `its partner ${s.partner} was not changed with it`
  if (s.kind === 'gate-file') return `guards the rule: ${s.invariant}`
  if (s.kind === 'deleted') return 'deleted'
  return s.kind
}

// One plain sentence per file the turn edited: what changed in it that the ontology names.
function fileLine(f: StateFile): string {
  const what = f.signals.map(signalText)
  if (what.length) return `${base(f.path)}: ${what.join('; ')}`
  return `${base(f.path)}: governed by ${f.domains.join(', ')}, nothing the ontology names changed`
}

// One plain sentence per check: what it looked at, what it found, and when.
const CHECK_LABEL: Record<Stage, string> = {
  validate: 'Ontology file',
  edit: 'Last edit',
  stop: 'End of turn',
  commit: 'Last commit',
  ci: 'CI',
}

type Tone = 'good' | 'bad' | 'none'

function plural(n: number, word: string): string {
  return `${n} ${word}${n === 1 ? '' : 's'}`
}

function checkLine(stage: Stage, r: StateRecord | undefined, resolved?: string): { text: string; tone: Tone } {
  const label = CHECK_LABEL[stage]
  if (!r) return { text: `${label}: not run yet`, tone: 'none' }
  const when = `  ${clock(r.ts)}`
  if (stage === 'validate') {
    const e = r.errors ?? 0
    const w = r.warnings ?? 0
    if (e) return { text: `${label}: ${plural(e, 'error')}${when}`, tone: 'bad' }
    return { text: `${label}: well-formed, ${w ? plural(w, 'warning') : 'no warnings'}${when}`, tone: 'good' }
  }
  if (r.skip) return { text: `${label}: gate skipped, ${r.skip}${when}`, tone: 'good' }
  const files = r.files ?? []
  const affecting = files.filter(f => f.tier === 'affecting').map(f => base(f.path))
  const onto = r.domains?.length ? r.domains.map(d => `ontology/${d}.md`).join(', ') : 'the ontology'
  if (r.exit !== 0) {
    const named = affecting.length ? affecting.join(', ') : 'governed code'
    const entities = [...new Set(files.flatMap(f => f.signals.map(s => s.entity).filter(Boolean)))]
    const what = entities.length ? ` changed ${entities.join(', ')}` : ' changed'
    if (stage === 'edit' && resolved) return { text: `${label}: ${named}${what}, resolved at ${clock(resolved)}${when}`, tone: 'good' }
    return { text: `${label}: ${named}${what}, ${onto} not updated${when}`, tone: 'bad' }
  }
  if (stage === 'edit') {
    const [one] = files
    const named = one ? (files.length === 1 ? base(one.path) : `${files.length} files`) : 'nothing governed'
    return { text: `${label}: ${named}, ontology unaffected${when}`, tone: 'good' }
  }
  if (r.ontology_changed) return { text: `${label}: ontology updated with the code${when}`, tone: 'good' }
  if (!files.length) return { text: `${label}: no governed code changed${when}`, tone: 'good' }
  return { text: `${label}: code and ontology in step${when}`, tone: 'good' }
}

// Latest edits: the edit checks of the most recent turn that had any. A stop check closes a
// turn, so the segment runs from the stop before the last edit check to the stop after it; a
// quiet turn (stop checks only) leaves it in view until a newer edit check starts a new one.
function latestEdits(list: StateRecord[]): { files: StateFile[]; at?: string } {
  let lastEdit = -1
  list.forEach((r, i) => {
    if (r.mode === 'touched') lastEdit = i
  })
  if (lastEdit === -1) return { files: [] }
  let from = 0
  let to = list.length
  list.forEach((r, i) => {
    if (stageOf(r) !== 'stop') return
    if (i < lastEdit) from = i + 1
    else if (i > lastEdit && to === list.length) to = i
  })
  const seen = new Map<string, StateFile>()
  for (const r of list.slice(from, to)) {
    if (r.mode !== 'touched') continue
    for (const f of r.files ?? []) seen.set(f.path, f)
  }
  return { files: [...seen.values()], at: list[lastEdit]?.ts }
}

// The affecting files in view: the latest edits, plus the last record's when it was affecting
// (a stop or commit check names files no edit check saw).
function inView(list: StateRecord[]): StateFile[] {
  const seen = new Map<string, StateFile>()
  for (const f of latestEdits(list).files) seen.set(f.path, f)
  const last = list.at(-1)
  if (last && last.tier === 'affecting') for (const f of last.files ?? []) seen.set(f.path, f)
  return [...seen.values()].filter(f => f.tier === 'affecting')
}

type Change = { name: string; change: string; path: string; diff?: string }
type Card = { entity: string; changes: Change[] }
type Rule = { text: string; gate: string | null; file: string }

function cards(files: StateFile[]): Card[] {
  const byEntity = new Map<string, Card>()
  for (const f of files) {
    for (const s of f.signals) {
      if (s.kind !== 'declaration' || !s.entity || !s.name) continue
      const card = byEntity.get(s.entity) ?? { entity: s.entity, changes: [] }
      card.changes.push({ name: s.name, change: s.change ?? 'changed', path: f.path, diff: s.diff })
      byEntity.set(s.entity, card)
    }
  }
  return [...byEntity.values()]
}

function statusLine(list: StateRecord[]): string {
  const last = list.at(-1)
  if (!last) return 'ontology: no checks yet'
  const entities = cards(inView(list)).map(c => c.entity)
  const tail = entities.length ? ` (${entities.join(', ')})` : ''
  return `ontology: ${verdict(last)}, ${detail(last)}${tail}`
}

// ---------- the ontology files (the same shapes ontology_lib.py reads) ----------

const ENTITY_RE = /^-\s+\*\*([^*]+)\*\*\s*[—-]\s*(.*)$/
const REL_RE = /\(\s*([A-Za-z0-9_]+)\s*\)\s*-\[\s*([A-Z0-9_]+)\s*\]->\s*\(\s*([A-Za-z0-9_]+)\s*\)/g
const GATE_RE = /\[gate:\s*([^\]]+)\]/
// Status bookkeeping beside a rule, as ontology_lib.py reads it: who confirmed it, or that it was inferred.
const STATUS_RE = /\[confirmed:\s*[^\]]+\]|\(inferred\)/g

function sections(body: string): Record<string, string[]> {
  const out: Record<string, string[]> = {}
  let current: string | undefined
  for (const line of body.split('\n')) {
    const m = /^##\s+(.+?)\s*$/.exec(line)
    if (m) current = m[1]
    else if (current) (out[current] ??= []).push(line)
  }
  return out
}

function parseOntology(file: string, text: string): Domain {
  let domain = file.replace(/\.md$/, '')
  let body = text
  if (text.startsWith('---')) {
    const end = text.indexOf('\n---', 3)
    if (end !== -1) {
      const dm = /^domain:\s*(.+)$/m.exec(text.slice(3, end))
      if (dm?.[1]) domain = dm[1].trim().replace(/^["']|["']$/g, '')
      body = text.slice(end + 4)
    }
  }
  const sec = sections(body)
  const entities: Record<string, string> = {}
  for (const line of sec['Entities'] ?? []) {
    const m = ENTITY_RE.exec(line.trim())
    if (m?.[1] && m[2] !== undefined) entities[m[1].trim()] = m[2].trim()
  }
  const relationships: Relationship[] = []
  for (const line of sec['Relationships'] ?? []) {
    if (!line.trim().startsWith('- ')) continue
    for (const m of line.matchAll(REL_RE)) {
      const tail = line.slice((m.index ?? 0) + m[0].length).replace(/`/g, '').trim()
      relationships.push({ from: m[1] ?? '', verb: m[2] ?? '', to: m[3] ?? '', cardinality: tail })
    }
  }
  // A short bare line between bullets names the group the bullets after it belong to;
  // a sentence of prose or a heading does not.
  const invariants: Invariant[] = []
  let group = 'General'
  for (const line of sec['Invariants'] ?? []) {
    const s = line.trim()
    if (!s) continue
    if (s.startsWith('- ')) {
      const g = GATE_RE.exec(s)
      invariants.push({ text: s.slice(2).replace(GATE_RE, '').replace(STATUS_RE, '').replace(/\s{2,}/g, ' ').trim(), gate: g?.[1]?.trim() ?? null, group })
    } else if (!s.startsWith('#') && s.length <= 48 && !/[.:]$/.test(s)) {
      group = s
    }
  }
  const disagreements = (sec['Disagreements'] ?? [])
    .map(l => l.trim())
    .filter(l => l.startsWith('- '))
    .map(l => l.slice(2).replace(/`/g, '').trim())
  return { domain, file, entities, relationships, invariants, disagreements }
}

function mentions(text: string, entity: string): boolean {
  return new RegExp(`\\b${entity}\\b`, 'i').test(text)
}

function describeEntity(doms: Domain[], entity: string): string | undefined {
  for (const d of doms) if (d.entities[entity] !== undefined) return d.entities[entity]
  return undefined
}

function chain(doms: Domain[], entity: string): Relationship[] {
  return doms.flatMap(d => d.relationships.filter(r => r.from === entity || r.to === entity))
}

// ---------- what the diff changed, and which rules name it ----------

type Field = { name: string; change: 'added' | 'removed' | 'changed' }
const FIELD_RE = /^[+-]\s*(?:readonly\s+|public\s+|private\s+|protected\s+)?([A-Za-z_]\w*)\s*\??\s*[:=]/

function changedLines(diff: string): string[] {
  return diff.split('\n').filter(l => /^[+-]/.test(l) && !/^(\+\+\+|---)/.test(l))
}

// The fields the diff added, removed or changed: a name on a +/- line ahead of `:` or `=`.
function fieldsOf(card: Card): Field[] {
  const plus = new Set<string>()
  const minus = new Set<string>()
  for (const c of card.changes) {
    for (const line of changedLines(c.diff ?? '')) {
      const m = FIELD_RE.exec(line)
      if (m?.[1]) (line.startsWith('+') ? plus : minus).add(m[1])
    }
  }
  const out: Field[] = []
  for (const name of plus) out.push({ name, change: minus.has(name) ? 'changed' : 'added' })
  for (const name of minus) if (!plus.has(name)) out.push({ name, change: 'removed' })
  return out
}

function names(text: string, fields: Field[]): boolean {
  return fields.some(f => new RegExp(`\\b${f.name}\\b`).test(text))
}

// A declaration added or deleted outright, or one with no diff, puts everything about the entity at risk.
function wholeEntity(card: Card): boolean {
  return card.changes.some(c => c.change !== 'changed' || !c.diff)
}

function rulesAtRisk(about: Rule[], card: Card, fields: Field[]): Rule[] {
  return wholeEntity(card) ? about : about.filter(r => names(r.text, fields))
}

function linksAtRisk(links: Relationship[], card: Card, fields: Field[]): Relationship[] {
  if (wholeEntity(card)) return links
  const tokens = new Set<string>()
  for (const c of card.changes) for (const l of changedLines(c.diff ?? '')) for (const m of l.matchAll(/[A-Za-z_]\w*/g)) tokens.add(m[0])
  return links.filter(r => names(r.cardinality, fields) || tokens.has(r.from) || tokens.has(r.to))
}

// Added fields that nothing in the ontology names: no rule, relationship or entity line.
function unknownFields(doms: Domain[], fields: Field[]): Field[] {
  const texts = doms.flatMap(d => [
    ...d.invariants.map(i => i.text),
    ...d.relationships.map(r => r.cardinality),
    ...Object.values(d.entities),
  ])
  return fields.filter(f => f.change === 'added' && !texts.some(t => names(t, [f])))
}

function plain(text: string): string {
  return text.replace(/`/g, '')
}

function fieldNames(fields: Field[]): string {
  return fields.map(f => f.name).join(', ')
}

function describeFields(fields: Field[]): string {
  const verb = { added: 'adds', removed: 'removes', changed: 'changes' } as const
  const parts = (['added', 'removed', 'changed'] as const)
    .map(k => ({ k, list: fields.filter(f => f.change === k) }))
    .filter(x => x.list.length)
    .map(x => `${verb[x.k]} ${fieldNames(x.list)}`)
  return parts.length ? `It ${parts.join(', ')}.` : ''
}

function freshNote(where: string, fresh: Field[]): string | undefined {
  if (!fresh.length) return undefined
  const one = fresh.length === 1
  return `${fieldNames(fresh)} ${one ? 'is' : 'are'} new to the code: no rule in ${where} names ${one ? 'it' : 'them'}.`
}

// ---------- issues: what the person can act on ----------

type Issue = {
  id: string
  level: 'error' | 'warning'
  title: string
  entity?: string
  note?: string
  /** A failing test's output, shown as the evidence under the title. */
  output?: string
  rules: Rule[]
  fix: string
  explore: string
}

function hash(s: string): string {
  let h = 5381
  for (let i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) | 0
  return (h >>> 0).toString(36)
}

function domainFile(doms: Domain[], entity: string): string | undefined {
  for (const d of doms) if (d.entities[entity] !== undefined) return d.file
  return undefined
}

function rulesFor(doms: Domain[], entity: string): Rule[] {
  return doms.flatMap(d => d.invariants.filter(i => mentions(i.text, entity)).map(i => ({ ...i, file: d.file })))
}

function quoted(rules: Rule[]): string {
  return rules.length ? rules.map(r => `"${r.text}"`).join('; ') : 'no rule names it yet'
}

function disagreementsFor(doms: Domain[], entity: string): string[] {
  return doms.flatMap(d => d.disagreements.filter(line => mentions(line, entity)))
}

// The seed of an "Explore issue" chat: the rules as the ontology states them, what enforces
// each (its gate), and where the code already disagrees with itself about the entity.
function explorePrompt(subject: string, rules: Rule[], disagreements: string[]): string {
  const ruleLines = rules.length
    ? rules.map(r => `- ${r.text} (${r.gate ? `gate: ${r.gate}` : 'no gate'})`).join('\n')
    : '- (no rule in the ontology names it yet)'
  const disagreementLines = disagreements.length
    ? `\nWhere the code already disagrees with itself:\n${disagreements.map(d => `- ${d}`).join('\n')}`
    : ''
  return `Let's brainstorm this ontology issue without editing any file. ${subject}\n\nThe rules involved, as the ontology states them, with what enforces each:\n${ruleLines}${disagreementLines}\n\nWalk through it with me: what the rule means in the field, whether the code as it stands can break it, what a gate would have to check, and what is still unclear. Ask me one question at a time where my judgment is needed.`
}

// An affecting edit is an open issue until a later stop or commit check passed: the
// ontology was updated, or the change left the worktree.
function editStillOpen(list: StateRecord[]): StateRecord | undefined {
  let lastEdit = -1
  list.forEach((r, i) => {
    if (r.mode === 'touched') lastEdit = i
  })
  if (lastEdit === -1) return undefined
  for (const r of list.slice(lastEdit + 1)) if (r.mode === 'changed' && r.exit === 0 && !r.skip) return undefined
  return list[lastEdit]
}

// When the last edit's issue closed: the first later check that passed.
function resolvedAt(list: StateRecord[]): string | undefined {
  let lastEdit = -1
  list.forEach((r, i) => {
    if (r.mode === 'touched') lastEdit = i
  })
  if (lastEdit === -1) return undefined
  return list.slice(lastEdit + 1).find(r => r.mode === 'changed' && r.exit === 0 && !r.skip)?.ts
}

// An edit to the file that enforces a rule (its gate) puts that rule at risk even when no entity's
// type changed: the card names the rule and offers the two honest answers, update it or mark the
// change rule-neutral.
function gateIssues(files: StateFile[], doms: Domain[], blocked: boolean): Issue[] {
  return files.flatMap(f =>
    f.signals.filter(s => s.kind === 'gate-file' && s.invariant).map(s => {
      const text = plain(s.invariant!)
      const domain = f.domains[0]
      const where = domain ? `ontology/${domain}.md` : 'the ontology'
      const stored = doms.flatMap(d => d.invariants.map(i => ({ ...i, file: d.file }))).find(i => plain(i.text) === text)
      const rule: Rule = stored ?? { text, gate: base(f.path), file: domain ? `${domain}.md` : '' }
      const named = doms.flatMap(d => Object.keys(d.entities).filter(e => mentions(text, e)))
      const title = blocked
        ? `${base(f.path)} enforces the rule "${text}", and ${where} was not updated.`
        : `${base(f.path)} enforces the rule "${text}"; check the rule still holds.`
      const fix = `${f.path} enforces the rule "${text}" (${where}) and it changed. If the change alters what the rule allows, update the rule in ${where} with a Changelog line. If it does not (a log line, a rename, a refactor), say so and commit with ontology-skip: <reason> in the message. Run the rule's test${rule.gate ? ` (${rule.gate})` : ''} and confirm it passes.`
      const explore = explorePrompt(
        `${f.path} changed, and it is the gate for the rule "${text}" (${where}).`,
        [rule],
        named.flatMap(e => disagreementsFor(doms, e))
      )
      return { id: `gate:${hash(f.path + text)}`, level: blocked ? 'error' : 'warning', title, rules: [rule], fix, explore } as Issue
    })
  )
}

function issues(list: StateRecord[], doms: Domain[]): Issue[] {
  const out: Issue[] = []
  const edit = editStillOpen(list)
  if (edit) {
    const blocked = edit.exit !== 0 && !edit.skip
    for (const card of cards(inView(list))) {
      const file = domainFile(doms, card.entity)
      const where = file ? `ontology/${file}` : 'the ontology'
      const about = rulesFor(doms, card.entity)
      const fields = fieldsOf(card)
      const risk = rulesAtRisk(about, card, fields)
      const note = freshNote(where, unknownFields(doms, fields))
      const changes = card.changes.map(c => `${c.name} ${c.change} in ${c.path}`).join(', ')
      const names = card.changes.map(c => c.name).join(', ')
      const paths = [...new Set(card.changes.map(c => c.path))].join(', ')
      const what = describeFields(fields)
      const title = blocked
        ? `${changes}, and ${where} was not updated for ${card.entity}.`
        : `${changes}; the rules about ${card.entity} need a second look.`
      const fix = blocked
        ? `The change to ${names} in ${paths} affects the ontology entity ${card.entity}, and ${where} was not updated. ${what} Update ${where} so it describes this change: a line under Entities, Relationships or Invariants, plus a Changelog line. Then run python3 ontology/scripts/ontology_check.py --changed and confirm it passes.`
        : `The change to ${names} in ${paths} affects the ontology entity ${card.entity}. ${what} Check that each of these rules from ${where} still holds in the code, and add a gate where one is missing: ${quoted(risk.length ? risk : about)}.`
      const explore = explorePrompt(
        `The change to ${names} in ${paths} touches the entity ${card.entity} (${where}). ${what}${note ? ` ${note}` : ''}`,
        [...risk, ...about.filter(r => !risk.includes(r))],
        disagreementsFor(doms, card.entity)
      )
      out.push({ id: `edit:${hash(card.entity + changes)}`, level: blocked ? 'error' : 'warning', title, entity: card.entity, note, rules: risk, fix, explore })
    }
    out.push(...gateIssues(inView(list), doms, blocked))
  }
  const v = [...list].reverse().find(r => r.mode === 'validate')
  for (const line of v?.problems ?? []) {
    const m = /^(warn|error): ([^:]+): (.*)$/.exec(line)
    const level = m?.[1] === 'error' ? 'error' : 'warning'
    const file = m?.[2] ?? 'the ontology'
    const rest = m?.[3] ?? line
    const g = /^invariant without a gate: (.*)$/.exec(rest)
    const title = g?.[1] ? `No gate: ${g[1]}` : rest
    const fix = g?.[1]
      ? `Write an executable gate for this invariant from ontology/${file}: "${g[1]}". Add the test or constraint that enforces it, run it, then record it on the invariant line as [gate: <name>] and add a Changelog line.`
      : `Fix this problem in ontology/${file}: ${rest}. Then run python3 ontology/scripts/ontology_check.py --validate.`
    const ruleText = g?.[1]
    const named = ruleText ? Object.keys(doms.find(d => d.file === file)?.entities ?? {}).filter(e => mentions(ruleText, e)) : []
    const explore = explorePrompt(
      ruleText ? `The rule "${ruleText}" (ontology/${file}) has no gate: nothing in the code enforces it.` : `The ontology file ontology/${file} reports: ${rest}`,
      ruleText ? [{ text: ruleText, gate: null, file }] : [],
      named.flatMap(e => disagreementsFor(doms, e))
    )
    out.push({ id: `validate:${hash(line)}`, level, title, rules: [], fix, explore })
  }
  for (const rule of ruleRuns(list)) {
    if (rule.status === 'pass') continue
    const where = `ontology/${rule.domain}.md`
    const tests = rule.tests.join(', ')
    const after = hitText(rule)
    const output = rule.runs.find(r => r.status !== 'pass' && r.output)?.output?.trim()
    const asRule: Rule = { text: rule.text, gate: tests || null, file: `${rule.domain}.md` }
    const named = Object.keys(doms.find(d => d.file === `${rule.domain}.md`)?.entities ?? {}).filter(e => mentions(rule.text, e))
    const failed = rule.status === 'fail'
    const title = failed
      ? `A rule's test fails after this change: ${plain(rule.text)}`
      : `${plain(rule.text)}: its test did not run after ${after}.`
    const fix = failed
      ? `The test ${tests} for the rule "${plain(rule.text)}" (${where}) fails after ${after}.${output ? ` Output: ${output}` : ''} Make the code satisfy the rule again, or if the rule itself is wrong, change the rule in ${where} with a Changelog line. Run the test and confirm it passes.`
      : `Run ${tests} and report whether the rule "${plain(rule.text)}" (${where}) still holds after ${after}. If it fails, make the code satisfy the rule again, or if the rule itself is wrong, change the rule in ${where} with a Changelog line.`
    const explore = explorePrompt(
      `The rule "${plain(rule.text)}" (${where}) is gated by ${tests}, which ${failed ? 'fails' : 'did not run'} after ${after}.`,
      [asRule],
      named.flatMap(e => disagreementsFor(doms, e))
    )
    out.push({ id: `rule:${rule.id}`, level: failed ? 'error' : 'warning', title, note: `${tests} after ${after}`, output: failed ? output : undefined, rules: [asRule], fix, explore })
  }
  return out.sort((a, b) => (a.level === b.level ? 0 : a.level === 'error' ? -1 : 1))
}

// The rules whose own tests the checker reran after the last change, because the diff changed a
// function those tests depend on.
function ruleRuns(list: StateRecord[]): RuleRun[] {
  return [...list].reverse().find(r => r.mode === 'changed')?.rules ?? []
}

/** "findItemsLargerThanOrder changed in fit.ts" */
function hitText(rule: RuleRun): string {
  const names = [...new Set(rule.hit.map(h => h.name))]
  const files = [...new Set(rule.hit.map(h => base(h.file)))]
  if (!names.length) return 'the change'
  return `${names.join(', ')} changed in ${files.join(', ')}`
}

async function leftIds($: EngineInterface): Promise<string[]> {
  try {
    const v = await $.store.get(LEFT_KEY)
    return Array.isArray(v) ? v.filter((x): x is string => typeof x === 'string') : []
  } catch {
    return []
  }
}

// ---------- loading ----------

// The project root, not the working directory: a shell `cd` in the session moves the
// latter, and the state file and ontology/ live at the root.
async function projectRoot($: EngineInterface): Promise<string> {
  try {
    return await $.session.root()
  } catch {
    return '.'
  }
}

async function loadOntology($: EngineInterface): Promise<Domain[]> {
  try {
    const dir = `${await projectRoot($)}/${ONTOLOGY_DIR}`
    const entries = await $.fs.list(dir)
    const out: Domain[] = []
    for (const e of entries) {
      if (e.kind !== 'file' || !e.name.endsWith('.md') || e.name.toLowerCase() === 'readme.md') continue
      try {
        out.push(parseOntology(e.name, await $.fs.read(`${dir}/${e.name}`)))
      } catch {
        // an unreadable domain file is left out
      }
    }
    return out
  } catch {
    return []
  }
}

async function refresh($: EngineInterface): Promise<void> {
  let list: StateRecord[] = []
  try {
    const state = `${await projectRoot($)}/${STATE}`
    if (await $.fs.exists(state)) list = parseState(await $.fs.read(state))
  } catch {
    list = []
  }
  const doms = await loadOntology($)
  const ids = await leftIds($)
  await update($, records, () => list.slice(-500))
  await update($, ontology, () => doms)
  await update($, left, () => ids)
  $.ui.status(statusLine(list))
}

// ---------- the mod ----------

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'ontology', description: 'Open the ontology gates pane' })
    void $.ui.open({ id: PANE, title: 'Ontology' })
    await refresh($)
    return next(e)
  })

  on('command.run', { command: 'ontology' }, async $ => {
    await $.ui.open({ id: PANE, title: 'Ontology', focus: true })
    await refresh($)
    return { text: 'Ontology pane opened.' }
  })

  // The settings hooks run beneath: once next(e) settles the checker has written its record.
  on('classic.PostToolUse', async ($, e, next) => {
    const ran = await next(e)
    if (EDIT_TOOLS.has(e.tool_name)) await refresh($)
    return ran
  }).catch(($, e, next) => next(e))

  // A pressed action is "in chat" until the turn its prompt started has ended.
  on('turn.complete', async ($, e, next) => {
    const ran = await next(e)
    await update($, pressed, () => ({}))
    return ran
  }).catch(($, e, next) => next(e))

  on('classic.Stop', async ($, e, next) => {
    const ran = await next(e)
    await refresh($)
    return ran
  }).catch(($, e, next) => next(e))

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text, Code, Button } = $.ui.resolve(e)
    const list = await read($, records)
    const doms = await read($, ontology)
    const dismissed = await read($, left)
    const inChat = await read($, pressed)
    const views = await read($, view)
    const leftShown = await read($, showLeft)
    const unfolded = await read($, openGroups)
    const last = list.at(-1)
    const latest = new Map<Stage, StateRecord>()
    for (const r of list) {
      const s = stageOf(r)
      if (s) latest.set(s, r)
    }
    const all = issues(list, doms)
    const open = all.filter(i => !dismissed.includes(i.id))
    const leftCount = all.length - open.length
    const edits = latestEdits(list)
    const affected = cards(inView(list))

    // A rule as one block: a mark, the sentence with a hanging indent, its gate on a dim line.
    const ruleBlock = (r: Rule, hot: boolean, tag: boolean) => (
      <Box flexDirection="row" marginTop={1}>
        <Box width={3} flexShrink={0}>
          <Text color={!r.gate ? 'red' : hot ? 'yellow' : 'green'}>{!r.gate ? '✗' : hot ? '▲' : '✓'}</Text>
        </Box>
        <Box flexDirection="column" flexGrow={1} flexShrink={1}>
          <Text wrap="wrap" color={hot ? 'yellow' : undefined}>{plain(r.text)}{tag && hot ? '  (at risk)' : ''}</Text>
          {r.gate ? <Text dimColor wrap="wrap">gate  {plain(r.gate)}</Text> : <Text color="red">no gate</Text>}
        </Box>
      </Box>
    )
    const legend = <Text dimColor>✓ gated   ▲ at risk   ✗ no gate</Text>

    const act = async (id: string, what: Pressed, text: string) => {
      await update($, pressed, p => ({ ...p, [id]: what }))
      void $.prompt.submit({ text })
    }

    const leaveIt = async (id: string) => {
      const ids = [...new Set([...dismissed, id])]
      try {
        await $.store.set(LEFT_KEY, ids)
      } catch {
        // the dismissal still holds for this session
      }
      await update($, left, () => ids)
    }

    const takeBack = async (id: string) => {
      const ids = dismissed.filter(x => x !== id)
      try {
        await $.store.set(LEFT_KEY, ids)
      } catch {
        // the change still holds for this session
      }
      await update($, left, () => ids)
    }

    // One entity card: what changed, what it touches, the rules it puts at risk. Open or
    // closed decides the colours; the buttons are the issue box's, not the card's.
    const cardBody = (card: Card, isOpen: boolean) => {
      const desc = describeEntity(doms, card.entity)
      const file = domainFile(doms, card.entity)
      const where = file ? `ontology/${file}` : 'the ontology'
      const fields = fieldsOf(card)
      const about = rulesFor(doms, card.entity)
      const risk = rulesAtRisk(about, card, fields)
      const every = doms.flatMap(d => d.invariants.map(i => ({ ...i, file: d.file })))
      const links = chain(doms, card.entity)
      const riskLinks = linksAtRisk(links, card, fields)
      const note = freshNote(where, unknownFields(doms, fields))
      const v = views[card.entity] ?? DEFAULT_VIEW
      const shown = v.rules === 'risk' ? risk : v.rules === 'entity' ? about : every
      const shownLinks = v.relationships ? links : riskLinks
      const hot = isOpen ? 'yellow' : undefined
      const setView = (patch: Partial<View>) =>
        void update($, view, all => ({ ...all, [card.entity]: { ...(all[card.entity] ?? DEFAULT_VIEW), ...patch } }))
      const pick = (which: View['rules'], label: string, n: number) => (
        <Button
          key={`rules:${card.entity}:${which}`}
          label={`${v.rules === which ? '●' : '○'} ${label} (${n})`}
          variant={v.rules === which ? 'primary' : 'secondary'}
          onPress={() => setView({ rules: which })}
        />
      )
      return (
        <Box flexDirection="column">
          <Text bold>{card.entity}</Text>
          {desc && <Text dimColor wrap="wrap">{desc}</Text>}
          {!desc && doms.length > 0 && <Text dimColor>not an entity in ontology/</Text>}
          {card.changes.map(c => (
            <Box flexDirection="column" marginTop={1}>
              <Text color={hot} dimColor={!isOpen} wrap="wrap">{c.name} {c.change} in {c.path}</Text>
              {c.diff && !v.diff && changedLines(c.diff).map(l => (
                <Text color={isOpen ? (l.startsWith('+') ? 'green' : 'red') : undefined} dimColor={!isOpen} mono wrap="wrap">{'  '}{l}</Text>
              ))}
              {c.diff && v.diff && <Code source={c.diff} language="diff" format="diff" />}
            </Box>
          ))}
          {note && <Text color={hot} dimColor={!isOpen} wrap="wrap">{note}</Text>}
          <Box flexDirection="row" gap={1} marginTop={1}>
            <Text dimColor>rules</Text>
            {pick('risk', 'at risk', risk.length)}
            {pick('entity', `about ${card.entity}`, about.length)}
            {pick('all', 'all', every.length)}
          </Box>
          {shown.length === 0 && !(v.rules === 'risk' && note) && (
            <Text dimColor>{v.rules === 'risk' ? `  none: no rule about ${card.entity} names ${fields.length ? fieldNames(fields) : 'what changed'}` : '  none'}</Text>
          )}
          {shown.length > 0 && legend}
          {shown.map(r => ruleBlock(r, isOpen && risk.includes(r), v.rules !== 'risk'))}
          <Box flexDirection="row" gap={1} marginTop={1}>
            <Text dimColor>relationships</Text>
            <Button
              key={`links:${card.entity}`}
              label={`${v.relationships ? '☑' : '☐'} all (${links.length})`}
              onPress={() => setView({ relationships: !v.relationships })}
            />
            <Button
              key={`diff:${card.entity}`}
              label={`${v.diff ? '☑' : '☐'} full diff`}
              onPress={() => setView({ diff: !v.diff })}
            />
          </Box>
          {shownLinks.length === 0 && <Text dimColor>  none at risk</Text>}
          {shownLinks.map(r => (
            <Text mono wrap="wrap">
              {'  '}({r.from})-[{r.verb}]-&gt;({r.to}){r.cardinality ? `  ${r.cardinality}` : ''}
            </Text>
          ))}
        </Box>
      )
    }

    const actions = (issue: Issue) =>
      inChat[issue.id] ? (
        <Text dimColor italic>{inChat[issue.id] === 'fixing' ? 'Fixing in chat…' : 'Exploring in chat…'}</Text>
      ) : (
        <Box flexDirection="row" gap={1} marginTop={1}>
          <Button key={`fix:${issue.id}`} label="Fix it" variant="primary" onPress={() => void act(issue.id, 'fixing', issue.fix)} />
          <Button key={`look:${issue.id}`} label="Explore issue" onPress={() => void act(issue.id, 'exploring', issue.explore)} />
          <Button key={`leave:${issue.id}`} label="Leave it" onPress={() => void leaveIt(issue.id)} />
        </Box>
      )

    // Every rule, by the group the file puts it in; a group unfolds on request.
    const groups = doms.flatMap(d => {
      const names = [...new Set(d.invariants.map(i => i.group))]
      return names.map(name => ({ key: `${d.file}:${name}`, name, file: d.file, rules: d.invariants.filter(i => i.group === name).map(i => ({ ...i, file: d.file })) }))
    })
    const ruleCount = groups.reduce((n, g) => n + g.rules.length, 0)
    const ungated = groups.reduce((n, g) => n + g.rules.filter(r => !r.gate).length, 0)
    const toggleGroup = (key: string) =>
      void update($, openGroups, keys => (keys.includes(key) ? keys.filter(k => k !== key) : [...keys, key]))

    // The rules whose tests the last change reran: the passes are drawn here, the rest are issues above.
    const runs = ruleRuns(list)
    const passed = runs.filter(r => r.status === 'pass')
    const failedCount = runs.filter(r => r.status === 'fail').length
    const unrunCount = runs.length - passed.length - failedCount
    const runSummary = `${passed.length} of ${runs.length} pass after the last change${failedCount ? `, ${failedCount} fail` : ''}${unrunCount ? `, ${unrunCount} not run` : ''}`

    // Issues the person left alone: listed on request, each with a way back.
    const leftIssues = all.filter(i => dismissed.includes(i.id))
    const closedAt = resolvedAt(list)

    return (
      <Box flexDirection="column">
        <Text bold>Ontology gates</Text>
        {!last && <Text dimColor>no checks yet: edit a governed file or run the checker</Text>}
        {last && open.length === 0 && <Text color="green" bold>CLEAN  no open issues</Text>}
        {open.map(issue => {
          const card = issue.entity ? affected.find(c => c.entity === issue.entity) : undefined
          return (
            <Box flexDirection="column" borderStyle="round" borderColor={issue.level === 'error' ? 'red' : 'yellow'} paddingX={1} marginTop={1}>
              <Box flexDirection="row" gap={1}>
                <Text bold color={issue.level === 'error' ? 'red' : 'yellow'}>{issue.level === 'error' ? 'ERROR' : 'WARNING'}</Text>
                <Text wrap="wrap">{issue.title}</Text>
              </Box>
              {card ? (
                <Box marginTop={1}>{cardBody(card, true)}</Box>
              ) : (
                <Box flexDirection="column">
                  {issue.note && <Text color="yellow" wrap="wrap">{issue.note}</Text>}
                  {issue.output && <Text color="red" wrap="wrap">{issue.output}</Text>}
                  {issue.rules.length > 0 && !issue.id.startsWith('rule:') && <Text dimColor>rules at risk: they name what changed</Text>}
                  {issue.rules.map(r => ruleBlock(r, true, false))}
                </Box>
              )}
              {actions(issue)}
            </Box>
          )
        })}
        {leftCount > 0 && (
          <Box flexDirection="row" gap={1} marginTop={1}>
            <Text dimColor>{leftCount} left alone</Text>
            <Button key="left:toggle" label={leftShown ? 'Hide' : 'Show'} onPress={() => void update($, showLeft, v => !v)} />
          </Box>
        )}
        {leftShown && leftIssues.map(issue => {
          const card = issue.entity ? affected.find(c => c.entity === issue.entity) : undefined
          return (
            <Box flexDirection="column" borderStyle="round" borderDimColor paddingX={1} marginTop={1}>
              <Box flexDirection="row" gap={1}>
                <Text bold dimColor>LEFT ALONE</Text>
                <Text dimColor wrap="wrap">{issue.title}</Text>
              </Box>
              {card && <Box marginTop={1}>{cardBody(card, false)}</Box>}
              <Box marginTop={1}>
                <Button key={`back:${issue.id}`} label="Take it back" onPress={() => void takeBack(issue.id)} />
              </Box>
            </Box>
          )
        })}
        {runs.length > 0 && (
          <Box flexDirection="column" borderStyle="round" borderDimColor paddingX={1} marginTop={1}>
            <Box flexDirection="row" gap={1}>
              <Text bold dimColor>RULES RUN</Text>
              <Text dimColor>{runSummary}</Text>
            </Box>
            {passed.map(r => (
              <Box flexDirection="column">
                <Text color="green" wrap="wrap">✓ {plain(r.text)}</Text>
                <Text dimColor wrap="wrap">  {r.tests.join(', ')} after {hitText(r)}</Text>
              </Box>
            ))}
          </Box>
        )}
        {groups.length > 0 && (
          <Box flexDirection="column" borderStyle="round" borderDimColor paddingX={1} marginTop={1}>
            <Box flexDirection="row" gap={1}>
              <Text bold dimColor>RULES</Text>
              <Text dimColor>{ruleCount} in {[...new Set(groups.map(g => `ontology/${g.file}`))].join(', ')}, {ungated ? `${ungated} without a gate` : 'every one gated'}</Text>
            </Box>
            {groups.map(g => {
              const isOpen = unfolded.includes(g.key)
              const missing = g.rules.filter(r => !r.gate).length
              return (
                <Box flexDirection="column" marginTop={1}>
                  <Box flexDirection="row" gap={1}>
                    <Button key={`group:${g.key}`} label={`${isOpen ? '▾' : '▸'} ${g.name} (${g.rules.length})`} onPress={() => toggleGroup(g.key)} />
                    {missing > 0 && <Text color="red">{missing} without a gate</Text>}
                  </Box>
                  {isOpen && g.rules.map(r => ruleBlock(r, false, false))}
                </Box>
              )
            })}
          </Box>
        )}
        <Box flexDirection="column" borderStyle="round" borderDimColor paddingX={1} marginTop={1}>
          <Box flexDirection="row" gap={1}>
            <Text bold dimColor>EVIDENCE</Text>
            <Text dimColor>what each check saw, newest result per check</Text>
          </Box>
          {STAGES.map(stage => {
            const line = checkLine(stage, latest.get(stage), stage === 'edit' ? closedAt : undefined)
            if (line.tone === 'none') return <Text dimColor wrap="wrap">{line.text}</Text>
            return <Text color={line.tone === 'bad' ? 'red' : 'green'} wrap="wrap">{line.text}</Text>
          })}
          <Box marginTop={1}>
            <Text bold dimColor>EDITED{edits.at ? `  ${clock(edits.at)}` : ''}</Text>
          </Box>
          {edits.files.length === 0 && <Text dimColor>no governed file edited yet</Text>}
          {edits.files.map(f => (
            <Text color={f.tier === 'affecting' && open.length ? 'yellow' : undefined} dimColor={!open.length} wrap="wrap">{fileLine(f)}</Text>
          ))}
        </Box>
      </Box>
    )
  })
}
