export const meta = {
  name: 'implement',
  description: 'Go units of work: implement → gate → review → verify → fix → re-gate, each stage on its own tier.',
  whenToUse:
    'When several independent units of Go work are already briefed and each would otherwise be driven implement → review → fix from the main loop. Units must touch disjoint files. Not for exploratory work, one-off edits, or writing the plan itself.',
  phases: [
    { title: 'Implement', detail: 'one implementer per unit; returns the paths it changed', model: 'opus' },
    { title: 'Gate', detail: "the project's check command, verdict only, one at a time", model: 'haiku' },
    { title: 'Review', detail: "strong-tier review of the unit's own paths", model: 'opus' },
    { title: 'Verify', detail: 'one refuter per finding', model: 'sonnet' },
    { title: 'Fix', detail: "confirmed findings, in the unit's paths only", model: 'opus' },
    { title: 'Re-gate', detail: 'the check command again after a fix', model: 'haiku' },
  ],
}

// Why a script: driven from the main loop, every hop below is a full-context turn
// at the session tier, and every intermediate result is re-read on every later
// turn. Here the hops are script variables; the caller pays to launch and to read
// the summary. Ported from ios-kit's implement (the scope and path-matching rules
// below are measured failures), without its rendered-evidence stage.
//
// Invoke with args (the Workflow tool's `args`, as JSON — not a string):
//   {
//     units: [
//       { id: 'feed-dedup', brief: '…the contract…' },
//       { id: 'reorg-proof', brief: '…', skills: ['fork-node-api', 'record-format'] },
//     ],
//     gate: 'make test-offline',     // the project's check; omitted = no Gate (a coverage hole)
//     base: 'origin/main',           // the ref each unit's diff is read against
//     implementer: 'blockchain-kit:golang-implementer', // any agent type; default below
//     reviewer: undefined,           // default: the workflow's own subagent, told not to edit
//     tiers: { review: 'sonnet' },   // override any stage's model; never above opus
//     fork: '/abs/path/to/bsc-geth', // set when the units are FORK work: see below
//   }
// A unit's `skills` are blockchain-kit skills its implementer, reviewer and fixer load
// by name: a subagent gets no skill by description. `go` is always loaded.
//
// One run is one tree. With `fork`, every unit is in the fork checkout: paths are
// relative to it, `gate` runs in it, `base` is a ref of it (mrinal/master), and
// `fork-ext-convention` is loaded beside `go`. A change that spans the fork and the
// bot is two runs, the fork's first.
//
// The gate is diff-scoped by the caller's choice of command. `make replay-parity` is
// not a per-unit gate: the caller runs it once, after the workflow, when a unit
// touched internal/{replay,trigger,strategy,state}.

const IMPL = {
  type: 'object',
  properties: {
    paths: { type: 'array', items: { type: 'string' }, description: 'every path this unit changed, repo-relative' },
    summary: { type: 'string', description: 'one line per path' },
  },
  required: ['paths', 'summary'],
}

const GATE = {
  type: 'object',
  properties: {
    green: { type: 'boolean', description: 'true only if the command exited 0' },
    verdict: { type: 'string', description: 'one line: pass/fail, elapsed, counts' },
    failingPaths: { type: 'array', items: { type: 'string' }, description: 'repo-relative source paths named by the failures, empty when green' },
    failingTail: { type: 'string', description: 'at most ten failing lines, empty when green' },
  },
  required: ['green', 'verdict'],
}

const FINDINGS = {
  type: 'object',
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          title: { type: 'string' },
          file: { type: 'string' },
          line: { type: 'number' },
          severity: { type: 'string', description: 'blocker | major | minor' },
          why: { type: 'string', description: 'the defect and the failure it causes' },
        },
        required: ['title', 'file', 'why'],
      },
    },
    enumerated: { type: 'string', description: 'what was covered, so a gap is visible' },
  },
  required: ['findings'],
}

const VERDICT = {
  type: 'object',
  properties: {
    refuted: { type: 'boolean', description: 'true only on positive evidence the finding does not hold' },
    reason: { type: 'string' },
  },
  required: ['refuted', 'reason'],
}

// Reviewers write repo-relative paths, implementers sometimes absolute; an exact
// match drops every finding and reads as a clean review. Match on a
// separator-aligned suffix.
const sameFile = (a, b) => {
  const norm = (s) => String(s || '').replace(/^\.\//, '').replace(/\\/g, '/')
  const [x, y] = [norm(a), norm(b)]
  if (!x || !y) return false
  return x === y || x.endsWith('/' + y) || y.endsWith('/' + x)
}

// One at a time, in arrival order: two gates building one module at once contend
// for its build cache, and a failure then belongs to neither unit.
const serial = () => {
  let tail = Promise.resolve()
  return (fn) => {
    const run = tail.then(fn, fn)
    tail = run.catch(() => {})
    return run
  }
}
const oneGate = serial()

const a = args || {}
const units = Array.isArray(a.units) ? a.units : null
const implementer = a.implementer || 'blockchain-kit:golang-implementer'
const reviewer = a.reviewer || null
const gateCmd = a.gate || ''
const base = a.base || ''
const fork = a.fork ? String(a.fork) : ''
const git = fork ? `git -C "${fork}"` : 'git'
const root = fork ? `the fork checkout, ${fork}` : 'the repository root'
const TIERS = Object.assign(
  { implement: 'opus', gate: 'haiku', review: 'opus', verify: 'sonnet', fix: 'opus' },
  a.tiers || {},
)

// The skills a stage loads by name. `go` always, the Ext convention for fork work;
// the unit names the rest.
const skillsOf = (unit) => {
  const always = fork ? ['go', 'fork-ext-convention'] : ['go']
  const named = [...always, ...((unit.skills || []).map((s) => String(s).replace(/^blockchain-kit:/, '')))]
  return [...new Set(named)].map((s) => `blockchain-kit:${s}`)
}
const loadLine = (unit) =>
  `Before reading or editing Go, load with the Skill tool and follow: ${skillsOf(unit).join(', ')}. `

// What an implementer may run. The fork is never built, vetted or tested whole.
const scopedGates = fork
  ? `Every path in this brief is under ${fork}, and every command names that tree: go -C "${fork}" …, ` +
    `${git} …, make -C "${fork}" …. Run only package-scoped gates there: go vet and go test -count=1 on ` +
    `the packages you touched, then make -C "${fork}" audit-ext. Never build, vet or test the whole fork. `
  : `Run only diff-scoped gates: go build ./..., go vet ./..., and go test -count=1 on the packages you touched. `

// What a reviewer holds a Go API in the diff to.
const apiRule = fork
  ? `This is the bsc-geth fork: every fork-added durable surface ends in Ext and lives in a *_ext.go ` +
    `file, and an edit inside an upstream function that deletes or restructures an upstream line is a ` +
    `finding. Upstream provenance is settled by \`${git} show v1.7.8:<path>\`, never by the suffix. `
  : `A go-ethereum API in the diff resolves to the pinned fork: check it with ` +
    `\`bsc-fork show <Symbol>\`, and an API with no fork file:line is a finding. `

// Where each unit got to, so a dropped unit says whether it left edits behind.
const reached = {}
const mark = (id, stage, detail) => {
  reached[id] = reached[id] || { stages: [] }
  reached[id].stages.push(stage)
  if (detail) Object.assign(reached[id], detail)
}
const owned = (id) => (reached[id] && reached[id].paths) || []

if (!units || units.length === 0) {
  log('no units passed — expected args {units:[{id, brief, skills?}], gate, base}')
  return { error: 'no units', units: 0 }
}
if (Object.values(TIERS).some((m) => /fable|mythos/i.test(String(m)))) {
  log('a tier above opus was named — this workflow runs opus and lower')
  return { error: 'tier above opus', units: units.length }
}
if (!gateCmd) log('no gate bound — Gate and Re-gate are skipped, a coverage hole')
if (!base) log('no base ref bound — refuters cannot diff, so they keep findings they cannot read')
log(`${units.length} unit(s) · tree=${fork || '(the project)'} · gate=${gateCmd || '(none)'} · base=${base || '(none)'} · implementer=${implementer}`)

const runGate = (unit, phase) =>
  oneGate(() =>
    agent(
      `Run exactly, from ${root}: ${gateCmd}\n` +
        `Report one line (pass/fail, elapsed, counts). A Go test line that says (cached) executed ` +
        `nothing: say so in the verdict. On failure list the repo-relative source paths ` +
        `the failures name, and at most ten failing lines — never the whole log. Do not fix anything.`,
      { label: `${phase.toLowerCase()}:${unit.id}`, phase, model: TIERS.gate, effort: 'low', schema: GATE },
    ),
  )

const results = await pipeline(
  units,

  // Implement.
  (unit) =>
    agent(
      `${unit.brief}\n\n` +
        loadLine(unit) +
        `Other units are being implemented in this working tree at the same time: touch only what this ` +
        `brief names, never revert or reformat a file you did not need to change, never touch go.mod or ` +
        `go.sum, and do not commit. ` +
        scopedGates +
        `Return every path you changed and a one-line summary of each.`,
      { label: `implement:${unit.id}`, phase: 'Implement', agentType: implementer, model: TIERS.implement, effort: 'medium', schema: IMPL },
    ).then((out) => {
      const paths = (out && out.paths) || []
      mark(unit.id, 'Implement', { wroteToTree: paths.length > 0, paths })
      return out
    }),

  // Gate. A red gate whose failures all lie outside this unit's paths is another
  // unit's half-finished work, not this one's defect: inconclusive, not red.
  async (built, unit) => {
    if (!gateCmd) {
      mark(unit.id, 'Gate', { gate: 'skipped' })
      return { green: true, skipped: true }
    }
    const g = await runGate(unit, 'Gate')
    const mine = owned(unit.id)
    const failing = (g && g.failingPaths) || []
    const elsewhere = g && !g.green && failing.length > 0 && !failing.some((f) => mine.some((p) => sameFile(p, f)))
    mark(unit.id, 'Gate', { gate: !g ? 'no answer' : g.green ? 'green' : elsewhere ? 'red elsewhere' : 'red' })
    if (elsewhere) log(`${unit.id}: gate red only in other paths (${failing.join(', ')}) — continuing, marked inconclusive`)
    return elsewhere ? { ...g, green: true, inconclusive: true } : g
  },

  // Review.
  (gate, unit) => {
    if (gate && gate.green === false) {
      mark(unit.id, 'Review', { reviewed: false })
      return { findings: [], enumerated: 'skipped — gate red', gateRed: gate }
    }
    const mine = owned(unit.id)
    return agent(
      `Review the change for unit "${unit.id}". Do not edit anything. Brief:\n${unit.brief}\n\n` +
        (mine.length
          ? `THIS UNIT CHANGED EXACTLY THESE PATHS:\n${mine.map((f) => `  ${f}`).join('\n')}\n` +
            `Read them with \`${git} diff ${base || 'HEAD'} -- <path>\` (and the new files whole). Other ` +
            `units are changing other paths in the same tree; a change outside this list is never a ` +
            `finding against this unit.\n\n`
          : `The implementer returned no path list, so this unit's boundary is unknown. Say so in ` +
            `"enumerated" and judge only what the brief names.\n\n`) +
        loadLine(unit) +
        `The go skill's rules (symbol routing, the reference-count rule, build constraints) apply to any ` +
        `claim that something is unused or unreferenced, and its review pitfalls are the classes to look ` +
        `for. ` +
        apiRule +
        `Enumerate the whole change and say in "enumerated" what you covered. Report defects, not ` +
        `preferences. An independent verifier refutes every finding before it costs a fix, so return ` +
        `candidates with their failure scenarios.`,
      { label: `review:${unit.id}`, phase: 'Review', ...(reviewer ? { agentType: reviewer } : {}), model: TIERS.review, effort: 'high', schema: FINDINGS },
    ).then((r) => {
      mark(unit.id, 'Review', { reviewed: true })
      return r
    })
  },

  // Verify. One refuter per finding.
  async (review, unit) => {
    const found = (review && review.findings) || []
    const verdicts = await parallel(
      found.map((f) => () =>
        agent(
          `Try to REFUTE this review finding about unit "${unit.id}".\n\n${f.title}\n` +
            `${f.file}${f.line ? ':' + f.line : ''}\n${f.why}\n\n` +
            (base ? `Read the change first: \`${git} diff ${base} -- ${f.file}\`.` : `No base ref was bound, so you cannot diff.`) +
            `\nThe brief:\n${unit.brief}\n\nSet refuted=true only on positive evidence — a quotable line, ` +
            `a guard already present, a type that makes it impossible. Being unable to read the change is ` +
            `not a refutation: say so and leave refuted=false.`,
          { label: `verify:${unit.id}:${f.file}`, phase: 'Verify', model: TIERS.verify, effort: 'high', schema: VERDICT },
          // a refuter that died refuted nothing: the finding stands
        ).then((v) => (v && v.refuted ? null : f), () => f),
      ),
    )
    const confirmed = verdicts.filter(Boolean)
    mark(unit.id, 'Verify')
    if (found.length) log(`${unit.id}: ${confirmed.length}/${found.length} review findings survived`)
    return { unit: unit.id, confirmed, review }
  },

  // Fix, then Re-gate. In-scope findings only: a finding about another path is a
  // report, never a work order — a fixer once "fixed" one by deleting work that
  // was not its own.
  async (checked, unit) => {
    const base_ = { unit: unit.id, review: checked.review }
    if (checked.confirmed.length === 0) return { ...base_, confirmed: [], fixed: null }
    const mine = owned(unit.id)
    const inScope = checked.confirmed.filter((f) => mine.length === 0 || !f.file || mine.some((p) => sameFile(p, f.file)))
    const outOfScope = checked.confirmed.filter((f) => !inScope.includes(f))
    if (outOfScope.length) log(`${unit.id}: ${outOfScope.length} finding(s) name paths outside the unit — reported, not fixed`)
    if (inScope.length === 0) {
      log(`${unit.id}: NONE of ${checked.confirmed.length} confirmed finding(s) matched the unit's paths [${mine.join(', ')}] — nothing fixed; check path conventions before reading this as clean`)
      return { ...base_, confirmed: [], fixed: null, outOfScope }
    }
    const list = inScope.map((f, i) => `${i + 1}. ${f.file}${f.line ? ':' + f.line : ''} — ${f.title}: ${f.why}`).join('\n')
    const fixed = await agent(
      `Fix these confirmed findings for unit "${unit.id}". Fix only these; do not refactor around them.\n\n${list}\n\n` +
        loadLine(unit) +
        (fork ? scopedGates : '') + // the paths below are relative to that tree
        `Edit ONLY: ${mine.join(', ') || '(the paths named above)'}. ` +
        `If a fix needs anything else, do not — say so. Deleting or reverting a change you did not make ` +
        `is never the fix. Do not commit.`,
      { label: `fix:${unit.id}`, phase: 'Fix', agentType: implementer, model: TIERS.fix, effort: 'medium' },
    )
    mark(unit.id, 'Fix')
    let regate = null
    if (gateCmd) {
      regate = await runGate(unit, 'Re-gate')
      mark(unit.id, 'Re-gate', { regate: regate && regate.green ? 'green' : 'red' })
      if (regate && !regate.green) log(`${unit.id}: RED after fix — ${regate.verdict}`)
    }
    return { ...base_, confirmed: inScope, fixed: Boolean(fixed), outOfScope, regate }
  },
)

const STAGES = ['Implement', 'Gate', 'Review', 'Verify', 'Fix', 'Re-gate']
const stalled = units
  .filter((u, i) => !results[i])
  .map((u) => {
    const r = reached[u.id] || { stages: [] }
    const last = r.stages[r.stages.length - 1]
    return { unit: u.id, reached: last || '(nothing)', wroteToTree: Boolean(r.wroteToTree), gate: r.gate || 'not run' }
  })
for (const s of stalled) {
  log(`${s.unit}: stopped after ${s.reached}` + (s.wroteToTree ? ` — edits ARE in the working tree (gate ${s.gate}), unreviewed` : ''))
}

const paritySensitive = /(^|\/)internal\/(replay|trigger|strategy|state)\//
const parityOwed = results
  .filter(Boolean)
  .filter(() => !fork) // the fork has no replay; its paths are not the bot's
  .filter((r) => ((reached[r.unit] || {}).paths || []).some((p) => paritySensitive.test(String(p))))
  .map((r) => r.unit)
if (parityOwed.length) log(`replay-parity is owed by the caller, once: ${parityOwed.join(', ')} touched a parity-sensitive package`)

return {
  units: units.length,
  completed: results.filter(Boolean).length,
  perUnit: results.filter(Boolean).map((r) => {
    const st = reached[r.unit] || {}
    return {
      unit: r.unit,
      paths: st.paths || [],
      gate: st.gate,
      confirmed: (r.confirmed || []).map((f) => `${f.file}: ${f.title}`),
      fixed: r.fixed,
      regate: st.regate || (r.fixed ? 'not run' : null),
      outOfScope: (r.outOfScope || []).map((f) => `${f.file}: ${f.title}`),
    }
  }),
  parityOwed,
  stalled,
  stages: STAGES,
}
