export type Signal = {
  kind: 'declaration' | 'parity' | 'gate-file' | 'deleted' | string
  name?: string
  entity?: string
  change?: string
  diff?: string
  partner?: string
  invariant?: string
}

export type StateFile = {
  path: string
  tier: 'touched' | 'affecting' | string
  signals: Signal[]
  domains: string[]
}

// One run of a rule's own test, as the checker records it after a change to a function the test depends on.
export type RuleTestRun = { test: string; status: 'pass' | 'fail' | string; output?: string }
export type RuleRun = {
  id: string
  text: string
  domain: string
  status: 'pass' | 'fail' | 'unrun' | string
  tests: string[]
  hit: { file: string; name: string }[]
  runs: RuleTestRun[]
}

export type StateRecord = {
  ts: string
  mode: 'validate' | 'touched' | 'changed' | string
  exit: number
  tier?: string
  files?: StateFile[]
  domains?: string[]
  ontology_changed?: boolean
  skip?: string | null
  base?: string | null
  staged?: boolean
  message?: string
  errors?: number
  warnings?: number
  problems?: string[]
  rules?: RuleRun[]
  changed_functions?: Record<string, string[]>
}

export type Pressed = 'fixing' | 'exploring'

// How one entity card is folded: which rules it lists, and whether it shows every relationship and the full diff.
export type View = { rules: 'risk' | 'entity' | 'all'; relationships: boolean; diff: boolean }

export type Relationship = { from: string; verb: string; to: string; cardinality: string }
export type Invariant = { text: string; gate: string | null; group: string }

export type Domain = {
  domain: string
  file: string
  entities: Record<string, string>
  relationships: Relationship[]
  invariants: Invariant[]
  disagreements: string[]
}

declare module 'claude-code' {
  interface PluginState {
    'ontology-observer': { records: StateRecord[]; ontology: Domain[]; left: string[]; pressed: Record<string, Pressed>; view: Record<string, View>; showLeft: boolean; openGroups: string[] }
  }
}
