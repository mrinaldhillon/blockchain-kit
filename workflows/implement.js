export const meta = {
  name: 'implement',
  description: 'Briefed Go units: parallel worktree lanes → one merged run branch → gate → one review → one fix round.',
  whenToUse:
    'When several independent units of Go work are already briefed, each with its own packages, and would otherwise be driven implement → merge → gate → review → fix from the main loop. Not for exploratory work, a one-off edit, or writing the plan itself.',
  phases: [
    { title: 'Lane', detail: 'one implementer per unit, each in its own worktree, committing on its lane branch', model: 'opus' },
    { title: 'Integrate', detail: 'merge the lane branches into the run branch in unit order; remove what merged', model: 'sonnet' },
    { title: 'Gate', detail: 'bk-gate on the merged tree; the script reads rc from the verdict line', model: 'haiku' },
    { title: 'Review', detail: 'one code-reviewer seat over head..HEAD', model: 'opus' },
    { title: 'Fix', detail: 'blocker and major findings together, one dispatch, one round', model: 'opus' },
    { title: 'Re-gate', detail: 'the gate again after the fix', model: 'haiku' },
  ],
}

// Why a script: driven from the main loop, every hop below is a full-context turn at
// the session tier, and every intermediate result is re-read on every later turn.
// Here the hops are script variables; the caller pays to launch and to read the
// return object. The contract is docs/design.md §7.
//
// Invoke with args (the Workflow tool's `args`, as JSON, not a string):
//   {
//     units: [
//       { id: 'feed-dedup', brief: '…the contract…', packages: ['internal/feeds'] },
//       { id: 'reorg-proof', brief: '…', packages: ['internal/state'], skills: ['record-format'] },
//     ],
//     branch: 'feat/x',              // the run branch, checked out in the session's tree
//     head: '<sha>',                 // its commit: every lane starts here
//     gate: 'make test-offline PKG=./internal/feeds/... ./internal/state/...',
//     fork: '/abs/path/to/bsc-geth', // set when the units are FORK work: see below
//     tiers: { review: 'session' },  // per-stage model; nothing above opus by name
//     project: '/abs/path/to/clone', // the session's project root, and
//     module: 'example.com/bot',     // the module its go.mod names: see below
//   }
// The script cannot read the filesystem, so the caller says what the project is.
// When `module` is github.com/ethereum/go-ethereum the session is rooted in the
// bsc-geth fork itself, and a run is refused before any agent starts when `fork` is
// unset or names `project` (compared as given, trailing slashes dropped, no symlink
// resolution): in-place fork runs are not supported yet. Without `module` that check
// is not made, and the run logs so.
// The project's .claude/settings.json must set worktree.baseRef to "head": under the
// default a lane starts at origin/<default-branch>, and the start check drops it.
//
// With `fork`, harness worktrees do not apply (they belong to the session's
// repository): lanes run one at a time in the fork checkout, each committing on
// `branch` there, which the caller cut from mrinal/dev and checked out. There is no
// Integrate stage, the reviewer's API rule is the Ext convention, and the default
// gate is `make audit-ext`. A change that spans the fork and the bot is two runs, the
// fork's first.
//
// Nothing is pushed and no PR is opened. `make replay-parity` is never run here:
// `owed.parity` tells the caller to run it once.

const IMPLEMENTER = 'blockchain-kit:golang-implementer'
const REVIEWER = 'blockchain-kit:code-reviewer'
const HOT_PATH = ['event', 'eventlog', 'trigger', 'strategy', 'state', 'replay', 'executor']
const PARITY = /(^|\/)internal\/(replay|trigger|strategy|state)\//
const GUARDED = /(^|\/)internal\/(event|eventlog|recorder|feeds|state|trigger|strategy|executor|bot)\//

const LANE = {
  type: 'object',
  properties: {
    branch: { type: 'string', description: '`git branch --show-current` where you worked' },
    start: { type: 'string', description: '`git rev-parse HEAD` before your first edit' },
    sha: { type: 'string', description: '`git rev-parse HEAD` when you finished; equal to start when you committed nothing' },
    paths: { type: 'array', items: { type: 'string' }, description: 'every path you changed, repo-relative' },
    gates: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          name: { type: 'string' },
          rc: { type: 'number' },
          line: { type: 'string', description: "bk-gate's verdict line, verbatim" },
        },
        required: ['name', 'rc', 'line'],
      },
    },
    summary: { type: 'string', description: 'one line per path' },
    handback: { type: 'string', description: 'set only when the brief did not answer a question: the question and the options' },
  },
  required: ['branch', 'start', 'sha', 'paths', 'gates', 'summary'],
}

const INTEGRATE = {
  type: 'object',
  properties: {
    merged: { type: 'array', items: { type: 'string' }, description: 'unit ids merged, in order' },
    conflicted: {
      type: 'array',
      items: {
        type: 'object',
        properties: { unit: { type: 'string' }, branch: { type: 'string' }, files: { type: 'array', items: { type: 'string' } } },
        required: ['unit', 'branch'],
      },
    },
    head: { type: 'string', description: '`git rev-parse HEAD` of the run branch when you finished' },
    unclaimed: {
      type: 'array',
      items: { type: 'object', properties: { worktree: { type: 'string' }, branch: { type: 'string' } }, required: ['worktree'] },
    },
    error: { type: 'string', description: 'set only when step 1 failed and nothing was merged' },
  },
  required: ['merged', 'conflicted', 'head'],
}

const GATE = {
  type: 'object',
  properties: {
    line: { type: 'string', description: "bk-gate's first output line, verbatim" },
    rc: { type: 'number' },
    tail: { type: 'string', description: 'the lines bk-gate printed after the first, empty when green' },
  },
  required: ['line', 'rc'],
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
        required: ['title', 'file', 'severity', 'why'],
      },
    },
    enumerated: { type: 'string', description: 'every changed path with what was checked, so a gap is visible' },
  },
  required: ['findings', 'enumerated'],
}

const FIX = {
  type: 'object',
  properties: {
    sha: { type: 'string', description: '`git rev-parse HEAD` when you finished' },
    paths: { type: 'array', items: { type: 'string' } },
    fixed: { type: 'array', items: { type: 'number' }, description: 'the numbers of the findings you fixed' },
    summary: { type: 'string' },
  },
  required: ['sha', 'paths', 'fixed'],
}

const a = args || {}
const units = Array.isArray(a.units) ? a.units : []
const branch = a.branch ? String(a.branch) : ''
const head = a.head ? String(a.head) : ''
const fork = a.fork ? String(a.fork) : ''
const project = a.project ? String(a.project) : ''
const projectModule = a.module ? String(a.module) : ''
const gateCmd = a.gate ? String(a.gate) : fork ? 'make audit-ext' : ''
const TIERS = Object.assign({ lane: 'opus', integrate: 'sonnet', gate: 'haiku', review: 'opus', fix: 'opus' }, a.tiers || {})

const git = fork ? `git -C "${fork}"` : 'git'
const tree = fork ? `the fork checkout ${fork}` : "the repository root (the session's tree, not a worktree)"
const normPkg = (p) => String(p).replace(/^\.\//, '').replace(/\/\.\.\.$/, '').replace(/\/+$/, '')
const pkgsOf = (unit) => (Array.isArray(unit.packages) ? unit.packages.map(normPkg).filter(Boolean) : [])
// A lane reports a full SHA and the caller may pass a short one.
const sameSha = (x, y) => {
  const [p, q] = [String(x || '').trim().toLowerCase(), String(y || '').trim().toLowerCase()]
  return p.length >= 7 && q.length >= 7 && (p.startsWith(q) || q.startsWith(p))
}
// 'session' is the one way to run a stage above opus: the review seat, at the tier
// the caller is already paying for.
const modelOf = (stage) => (TIERS[stage] === 'session' ? {} : { model: TIERS[stage] })

const result = (over) =>
  Object.assign(
    { merged: [], conflicted: [], handbacks: [], stalled: [], gate: null, findings: { fixed: [], open: [] }, owed: { parity: [], read: [] }, head },
    over,
  )

// Refusals, before any agent runs.
const refuse = (error, detail) => {
  log(`refused: ${error}`)
  return { error, ...(detail || {}) }
}
if (units.length === 0) return refuse('no units', { expected: '{units:[{id, brief, packages?, skills?}], branch, head, gate, fork?, tiers?, project?, module?}' })
const bare = (p) => String(p).replace(/\/+$/, '')
if (projectModule === 'github.com/ethereum/go-ethereum' && (!fork || (project && bare(fork) === bare(project)))) {
  return refuse(
    'This project is the bsc-geth fork; in-place fork runs are not supported yet (kit PR B). Dispatch ' +
      'blockchain-kit:golang-implementer by hand, package-scoped, or run implement from the prediction-bot clone ' +
      'with `fork` set.',
    { project, module: projectModule, fork },
  )
}
if (!projectModule) log('no module given — whether this project is the bsc-geth fork is unchecked')
const bad = units.filter((u) => !u || !u.id || !u.brief)
if (bad.length) return refuse('a unit lacks id or brief', { count: bad.length })
const ids = units.map((u) => String(u.id))
if (new Set(ids).size !== ids.length) return refuse('unit ids are not unique', { ids })
if (!branch || !head) return refuse('branch and head are required', { branch, head })
const above = Object.entries(TIERS).filter(([stage, m]) => /fable|mythos/i.test(String(m)) || (m === 'session' && stage !== 'review'))
if (above.length) return refuse('tier above opus', { tiers: Object.fromEntries(above), allowed: "opus and lower by name; 'session' for review only" })
const owners = {}
for (const u of units) for (const p of new Set(pkgsOf(u))) (owners[p] = owners[p] || []).push(String(u.id))
const shared = Object.entries(owners).filter(([, who]) => who.length > 1).map(([pkg, who]) => ({ package: pkg, units: who }))
if (shared.length) return refuse('units share a package', { shared })
const blind = units.filter((u) => pkgsOf(u).length === 0).map((u) => String(u.id))
if (blind.length) log(`no packages declared for ${blind.join(', ')} — their overlap with other units is unchecked`)
if (!gateCmd) log('no gate bound — Gate and Re-gate are skipped, a coverage hole')
log(`${units.length} unit(s) · tree=${fork || '(the project)'} · branch=${branch} @ ${head} · gate=${gateCmd || '(none)'}`)

// The skills a stage loads by name: a subagent gets none by description. `go`
// always, the Ext convention for fork work, the hot-path skill when a unit's
// packages reach the hot-path set, and whatever the unit names.
const skillsOf = (unit) => {
  const hot = !fork && pkgsOf(unit).some((p) => HOT_PATH.some((h) => p === `internal/${h}` || p.startsWith(`internal/${h}/`)))
  const named = [
    'go',
    ...(fork ? ['fork-ext-convention'] : []),
    ...(hot ? ['hot-path-determinism'] : []),
    ...(unit.skills || []).map((s) => String(s).replace(/^blockchain-kit:/, '')),
  ]
  return [...new Set(named)].map((s) => `blockchain-kit:${s}`)
}
const loadLine = (list) => `Before reading or editing Go, load with the Skill tool and follow: ${list.join(', ')}. `
const allSkills = [...new Set(units.flatMap(skillsOf))]

const laneGates = fork
  ? `Every path in this brief is under ${fork}, and every command names that tree: go -C "${fork}" …, ${git} …, ` +
    `bk-gate -C "${fork}" <name> -- <command>. Gates are package-scoped: go vet and go test -count=1 on the packages ` +
    `you touched, then make audit-ext. Never build, vet or test the whole fork. `
  : `Gates are package-scoped and run through bk-gate: bk-gate build -- go build ./..., bk-gate vet -- go vet ./..., ` +
    `and bk-gate test -- go test -count=1 <the packages you touched>. `

const lanePrompt = (unit, startAt) =>
  `You are a lane of the blockchain-kit:implement workflow, unit "${unit.id}". The section "As a lane of the ` +
  `implement workflow" in your instructions governs: report your start, run gates through bk-gate, commit on your ` +
  `branch, hand back rather than guess.\n\n` +
  (fork
    ? `This is a serial fork run. Work in ${fork} on branch ${branch}, which is checked out there. ` +
      `\`${git} rev-parse HEAD\` must print ${startAt} before your first edit. Commit on that branch with ${git}. ` +
      `A hand-back commits nothing and leaves the tree as you found it.\n\n`
    : `You are in your own git worktree on a branch the harness named. \`git rev-parse HEAD\` must print ${startAt} ` +
      `before your first edit. Other lanes are implementing other units in other worktrees: ` +
      (pkgsOf(unit).length ? `your packages are ${pkgsOf(unit).join(', ')} and nothing outside them is yours. ` : `touch only what the brief names. `) +
      `Never touch go.mod or go.sum.\n\n`) +
  loadLine(skillsOf(unit)) +
  laneGates +
  `\n\nThe brief:\n${unit.brief}`

const laneOpts = (unit) => ({
  label: `lane:${unit.id}`,
  phase: 'Lane',
  agentType: IMPLEMENTER,
  ...modelOf('lane'),
  effort: 'medium',
  schema: LANE,
  ...(fork ? {} : { isolation: 'worktree' }),
})

// Lane. Concurrent in worktrees; in a fork run serial, each lane starting where the
// last one ended, and the run stops at the first lane that dies or hands back: the
// checkout is shared, so what that lane left is the next lane's tree.
const lanes = []
if (fork) {
  let at = head
  let stopped = ''
  for (const unit of units) {
    if (stopped) {
      lanes.push({ unit, out: null, startAt: at, notStarted: stopped })
      continue
    }
    let out = null
    try {
      out = await agent(lanePrompt(unit, at), laneOpts(unit))
    } catch (err) {
      out = null
    }
    lanes.push({ unit, out, startAt: at })
    if (!out) stopped = `lane ${unit.id} died`
    else if (out.handback) stopped = `lane ${unit.id} handed back`
    else at = out.sha
  }
} else {
  const outs = await parallel(units.map((unit) => () => agent(lanePrompt(unit, head), laneOpts(unit))))
  units.forEach((unit, i) => lanes.push({ unit, out: outs[i] || null, startAt: head }))
}

const handbacks = []
const stalled = []
const mergeable = []
for (const { unit, out, startAt, notStarted } of lanes) {
  const id = String(unit.id)
  if (notStarted) {
    stalled.push({ unit: id, stage: 'Lane', reason: `not started: ${notStarted}`, branch: null })
  } else if (!out) {
    stalled.push({
      unit: id,
      stage: 'Lane',
      reason: 'the lane died',
      branch: null,
      left: fork ? `possibly uncommitted edits in ${fork} on ${branch}` : 'possibly a worktree and a worktree-wf_* branch: see `unclaimed`',
    })
  } else if (!sameSha(out.start, startAt)) {
    stalled.push({ unit: id, stage: 'Lane', reason: `started at ${out.start}, not ${startAt} — dropped (worktree.baseRef must be "head")`, branch: out.branch, sha: out.sha })
  } else if (out.handback) {
    handbacks.push({ unit: id, branch: out.branch, sha: out.sha, handback: out.handback })
  } else if ((out.gates || []).some((g) => g.rc !== 0)) {
    const red = out.gates.find((g) => g.rc !== 0)
    handbacks.push({ unit: id, branch: out.branch, sha: out.sha, handback: `the lane returned a red gate: ${red.line}` })
  } else if (sameSha(out.sha, out.start)) {
    stalled.push({ unit: id, stage: 'Lane', reason: 'returned without a commit and without a hand-back', branch: out.branch })
  } else {
    mergeable.push({ unit: id, branch: out.branch, sha: out.sha, paths: out.paths || [] })
  }
}
for (const h of handbacks) log(`${h.unit}: handed back, not merged — ${h.handback}`)
for (const s of stalled) log(`${s.unit}: ${s.reason}`)

if (mergeable.length === 0) {
  log('no lane is mergeable — nothing to integrate, gate or review')
  return result({ handbacks, stalled })
}

// Integrate. Lane branches are visible from the session's tree. A conflict is never
// resolved here: the lane is left out, with its worktree and branch, for the caller.
let merged = mergeable
let conflicted = []
let tip = mergeable[mergeable.length - 1].sha
if (!fork) {
  const known = lanes.filter((l) => l.out && l.out.branch).map((l) => l.out.branch)
  let integrated = null
  try {
    integrated = await agent(
      `You integrate lane branches into a run branch. Work from ${tree}. Run git commands only: edit no file, ` +
        `resolve no conflict, push nothing, reset nothing.\n\n` +
        `1. \`git branch --show-current\` must print ${branch}, \`git rev-parse HEAD\` must print ${head}, and ` +
        `\`git status --porcelain --untracked-files=no\` must print nothing. If any of the three differs, merge ` +
        `nothing and return \`error\` with what you saw, merged and conflicted empty.\n` +
        `2. For each lane below, in this order: \`git merge --no-edit <branch>\`. If it fails: record the files ` +
        `from \`git diff --name-only --diff-filter=U\`, run \`git merge --abort\`, put the lane under conflicted, ` +
        `and go on to the next lane.\n` +
        `3. For every lane you merged: find its worktree in \`git worktree list --porcelain\` (the entry whose ` +
        `branch is refs/heads/<branch>), \`git worktree remove <path>\`, then \`git branch -d <branch>\`. Leave ` +
        `the worktree and the branch of a lane you did not merge.\n` +
        `4. From \`git worktree list --porcelain\`, report under unclaimed every worktree under .claude/worktrees/ ` +
        `whose branch is none of: ${known.join(', ') || '(none)'}.\n` +
        `5. Return merged (unit ids, in order), conflicted, head (\`git rev-parse HEAD\`) and unclaimed.\n\n` +
        `Lanes:\n${mergeable.map((m, i) => `  ${i + 1}. unit ${m.unit} — branch ${m.branch} — commit ${m.sha}`).join('\n')}`,
      { label: 'integrate', phase: 'Integrate', ...modelOf('integrate'), effort: 'low', schema: INTEGRATE },
    )
  } catch (err) {
    integrated = null
  }
  if (!integrated || integrated.error) {
    const reason = integrated ? `refused: ${integrated.error}` : 'the stage died'
    log(`Integrate ${reason} — the lane branches are unmerged`)
    stalled.push({ unit: null, stage: 'Integrate', reason, left: mergeable.map((m) => `${m.unit}: ${m.branch} @ ${m.sha}`) })
    return result({ handbacks, stalled })
  }
  const done = new Set((integrated.merged || []).map(String))
  merged = mergeable.filter((m) => done.has(m.unit))
  conflicted = (integrated.conflicted || []).map((c) => ({ unit: c.unit, branch: c.branch, files: c.files || [] }))
  const lost = mergeable.filter((m) => !done.has(m.unit) && !conflicted.some((c) => String(c.unit) === m.unit))
  for (const m of lost) stalled.push({ unit: m.unit, stage: 'Integrate', reason: 'neither merged nor reported as conflicted', branch: m.branch, sha: m.sha })
  for (const c of conflicted) log(`${c.unit}: conflicts with an earlier lane (${c.files.join(', ') || 'files not reported'}) — left on ${c.branch}`)
  if ((integrated.unclaimed || []).length) {
    stalled.push({ unit: null, stage: 'Lane', reason: 'worktrees no returned lane claims', left: integrated.unclaimed })
  }
  tip = integrated.head
  if (merged.length === 0) {
    log('every mergeable lane conflicted — nothing to gate or review')
    return result({ conflicted, handbacks, stalled, head: tip })
  }
}

const owed = () => {
  const touched = (re) => merged.filter((m) => m.paths.some((p) => re.test(String(p)))).map((m) => m.unit)
  const o = { parity: fork ? [] : touched(PARITY), read: fork ? [] : touched(GUARDED) }
  if (o.parity.length) log(`replay-parity is owed by the caller, once: ${o.parity.join(', ')}`)
  if (o.read.length) log(`the caller reads these diffs before landing: ${o.read.join(', ')}`)
  return o
}

// Gate. Green is rc == 0 parsed from the verdict line, never the agent's reading.
const runGate = async (phase) => {
  let g = null
  try {
    g = await agent(
      `Run exactly this one command from ${tree}, and nothing else:\n\n` +
        `  bk-gate ${fork ? `-C "${fork}" ` : ''}run -- ${gateCmd}\n\n` +
        `Return its first output line verbatim as line, the rc number in that line as rc, and the lines after ` +
        `it as tail. Do not fix anything, do not run it twice, do not read the out file. If bk-gate is not ` +
        `found, return line "bk-gate: not found" and rc 127.`,
      { label: phase.toLowerCase(), phase, ...modelOf('gate'), effort: 'low', schema: GATE },
    )
  } catch (err) {
    g = null
  }
  if (!g) return { rc: null, line: 'the gate stage died', green: false }
  const m = /^gate: \S+ rc=(-?\d+) t=\S+ out=\S+/.exec(String(g.line || '').trim())
  const rc = m ? Number(m[1]) : null
  return { rc, line: String(g.line || ''), tail: g.tail || '', green: rc === 0 }
}

let gate = { skipped: true, green: true, line: 'no gate bound' }
if (gateCmd) {
  gate = await runGate('Gate')
  if (gate.rc === null) stalled.push({ unit: null, stage: 'Gate', reason: `no verdict line: ${gate.line}`, left: `${branch} @ ${tip}, merged and ungated` })
  if (!gate.green) {
    log(`gate is not green (${gate.line}) — review skipped`)
    return result({ merged: merged.map((m) => m.unit), conflicted, handbacks, stalled, gate, owed: owed(), head: tip })
  }
}

// Review. One seat over the whole merged range.
const apiRule = fork
  ? `This is the bsc-geth fork: the four prediction-bot angles do not apply and the Ext convention does. `
  : `A go-ethereum API in the diff resolves to the pinned fork: check it with \`bsc-fork show <Symbol>\`. `
let review = null
try {
  review = await agent(
    `Review the range ${head}..HEAD in ${tree}: \`${git} diff ${head}..HEAD\`. It is the merged work of ` +
      `${merged.length} unit(s) on branch ${branch}. Do not edit anything and do not run a gate: the gate's ` +
      `verdict was \`${gate.line}\`.\n\n` +
      loadLine(allSkills) +
      apiRule +
      `\n\nThe contracts the diff was written against:\n\n` +
      merged.map((m) => `## unit ${m.unit}\n${units.find((u) => String(u.id) === m.unit).brief}`).join('\n\n'),
    { label: 'review', phase: 'Review', agentType: REVIEWER, ...modelOf('review'), effort: 'high', schema: FINDINGS },
  )
} catch (err) {
  review = null
}
if (!review) {
  log('the review stage died — the merged range is gated and UNREVIEWED')
  stalled.push({ unit: null, stage: 'Review', reason: 'the stage died', left: `${branch} @ ${tip}, gated and unreviewed` })
  return result({ merged: merged.map((m) => m.unit), conflicted, handbacks, stalled, gate, owed: owed(), head: tip })
}

const found = review.findings || []
const toFix = found.filter((f) => /^(blocker|major)$/i.test(String(f.severity || '').trim()))
const minor = found.filter((f) => !toFix.includes(f))
log(`review: ${found.length} finding(s), ${toFix.length} to fix`)
if (toFix.length === 0) {
  return result({ merged: merged.map((m) => m.unit), conflicted, handbacks, stalled, gate, findings: { fixed: [], open: minor }, owed: owed(), head: tip })
}

// Fix, then the gate again. One round: what remains is returned, not looped on.
let fix = null
try {
  fix = await agent(
    `You are the fix stage of the blockchain-kit:implement workflow. Work in ${tree} on branch ${branch}, at ` +
      `commit ${tip}. Fix these review findings and only these; do not refactor around them. Deleting or ` +
      `reverting a change is never the fix unless the finding says the change itself is the defect.\n\n` +
      toFix.map((f, i) => `${i + 1}. [${f.severity}] ${f.file}${f.line ? ':' + f.line : ''} — ${f.title}: ${f.why}`).join('\n') +
      `\n\n` +
      loadLine(allSkills) +
      laneGates +
      `Then make one commit on ${branch}${fork ? ` with ${git}` : ''}, as the section "As a lane of the implement ` +
      `workflow" in your instructions describes. Never touch go.mod or go.sum. Return the numbers of the ` +
      `findings you fixed; a finding you could not fix without leaving its file's contract stays unfixed and ` +
      `you say why in summary.`,
    { label: 'fix', phase: 'Fix', agentType: IMPLEMENTER, ...modelOf('fix'), effort: 'medium', schema: FIX },
  )
} catch (err) {
  fix = null
}
if (!fix) {
  log('the fix stage died — its edits may be uncommitted in the tree')
  stalled.push({ unit: null, stage: 'Fix', reason: 'the stage died', left: `possibly uncommitted edits in ${tree} on ${branch}` })
  return result({ merged: merged.map((m) => m.unit), conflicted, handbacks, stalled, gate, findings: { fixed: [], open: found }, owed: owed(), head: tip })
}

const fixedNos = new Set((fix.fixed || []).map(Number))
const fixed = toFix.filter((f, i) => fixedNos.has(i + 1))
const open = [...toFix.filter((f, i) => !fixedNos.has(i + 1)), ...minor]
if (fix.sha) tip = fix.sha
if ((fix.paths || []).length) merged.push({ unit: 'fix', branch, sha: fix.sha, paths: fix.paths })
if (gateCmd) {
  gate = await runGate('Re-gate')
  if (gate.rc === null) stalled.push({ unit: null, stage: 'Re-gate', reason: `no verdict line: ${gate.line}`, left: `${branch} @ ${tip}, fixed and ungated` })
  if (!gate.green) log(`RED after the fix: ${gate.line}`)
}
const o = owed()
return result({
  merged: merged.filter((m) => m.unit !== 'fix').map((m) => m.unit),
  conflicted,
  handbacks,
  stalled,
  gate,
  findings: { fixed, open },
  owed: o,
  head: tip,
})
