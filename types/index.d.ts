export type Signal = {
  kind: 'declaration' | 'parity' | 'gate-file' | 'deleted' | string
  name?: string
  entity?: string
  change?: string
  diff?: string
  partner?: string
  invariant?: string
  /** gate-file: the rule's gate text, why it fired, the functions around the change, its line ranges. */
  gate?: string
  match?: 'function' | 'file' | 'module' | 'unmapped' | 'same-file' | string
  gate_functions?: string[]
  functions?: string[]
  lines?: number[][]
}

export type StateFile = {
  path: string
  tier: 'touched' | 'affecting' | string
  signals: Signal[]
  domains: string[]
}

// One rule's recorded acceptance check, as ontology_evidence.py reports it in every changed record.
export type Verification = {
  domain: string
  rule: string
  status: 'passed' | 'failed' | 'stale' | 'not_run' | 'unavailable' | 'interrupted' | 'worktree_only' | string
  /** The argv ontology_verify.py ran, when a run was recorded. */
  command?: string[]
  exit?: number | null
  /** Absolute path of the log the run left; the pane reads its tail for a failed check. */
  output?: string
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
  /** The review gate's verdict: not_required, acknowledged, needs_review, skipped, unavailable. */
  review?: string
  verification?: Verification[]
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
    'ontology-observer': { records: StateRecord[]; ontology: Domain[]; left: string[]; pressed: Record<string, Pressed>; view: Record<string, View>; showLeft: boolean; openGroups: string[]; outputs: Record<string, string>; scripts: string | null }
  }
}
