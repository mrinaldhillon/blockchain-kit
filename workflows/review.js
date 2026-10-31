export const meta = {
  name: 'review',
  description: 'Intent-first review of one diff: what it was written to do and whether that logic is sound, then finders by angle against it, then an independent check of every finding.',
  whenToUse:
    'A pull request or branch in prediction-bot or bsc-geth reviewed against what it was written to do. Not for prose, and not for a diff an implement run already reviewed unless the user asks.',
  phases: [
    { title: 'Intent', detail: 'one seat: the contract from the PR, issue, ADR, plan or brief; whether that logic is sound for the domain; the diff size', model: 'fable' },
    { title: 'Find', detail: 'the conformance and domain finders at fable, and one to four more by angle at opus, by the size of the diff', model: 'fable' },
    { title: 'Check', detail: 'one independent checker per changed file with candidates, a verdict for each, by reading', model: 'fable' },
  ],
}

// Why intent first: a reviewer that works out what a function must compute while reading
// it checks the code against itself, and one whose angles are rule checks passes a defect
// that breaks no rule (prediction-bot#570: most of M8's defects broke none). Here the
// intent seat writes the contract down from the sources before any code is compared,
// and judges that logic against the domain; the finders then work against it, and a
// checker that did not raise a candidate decides whether it is real.
//
// Invoke with args (the Workflow tool's `args`, as JSON, not a string):
//   {
//     base: '<sha>',          // where the diff starts: the merge-base with the trunk
//     head: '<sha>',          // the commit under review; the session's tree is at it
//     pr: 1022,               // optional: the pull request whose body and links are the contract
//     contract: '…',          // optional: the brief or contract text, when there is no PR
//     project: '/abs/clone',  // filled with `module` by hooks/implement-args
//     module: 'example.com/bot',
//     tiers: { intent: 'fable', conformance: 'fable', domain: 'fable', find: 'opus', quality: 'sonnet', check: 'fable' },
//                             // fable only for intent, conformance, domain and check; nothing above opus elsewhere
//     maxChecks: 40,          // the most candidates checked; the rest come back unchecked
//     proceed: true,          // go past the pause after Intent (below); resume the paused run
//   }
// Two modes, from `module`: the bot (the four reserved angles of prediction-bot) and the
// fork (`module` is github.com/ethereum/go-ethereum: the Ext convention and the rebase
// landmines). The review is of the session's own repository; fork work seen from a
// prediction-bot session is reviewed from a session in the fork.
//
// The run pauses after Intent when the contract is in doubt (no source stated it, or a
// blocker in its logic) and returns it for the user; `proceed: true` goes on.
//
// Seats: one intent seat; the conformance finder plus ceil(changed lines / 150) more kept
// within 2..5, the domain finder always one of them; one checker per changed file that has
// candidates, eight candidates at most each, `maxChecks` candidates in all. Fable wherever a
// wrong judgment misdirects or silently drops something: the contract and its soundness, the
// mapping of code to intent, the project's invariants and every checker, whose refutal drops
// a finding. Opus for the pattern angles; sonnet for quality when it has its own seat.
// Nothing is edited, built or run; the return is the contract as the intent seat read it,
// every candidate that survived its check with the verdict that decided it, what was
// refuted, merged as a duplicate or left unchecked and why, and the coverage.

const SEAT = 'blockchain-kit:review-seat'
const UPSTREAM = 'github.com/ethereum/go-ethereum'
const SEVERITY = { blocker: 0, major: 1, minor: 2 }

const ITEM = {
  type: 'object',
  properties: {
    title: { type: 'string' },
    file: { type: 'string', description: 'repo-relative; empty when the finding is about the contract alone' },
    line: { type: 'number', description: 'the line at head' },
    severity: { type: 'string', description: 'blocker | major | minor' },
    item: { type: 'string', description: 'the contract item it concerns (C<n>), or none' },
    why: { type: 'string', description: 'the defect' },
    scenario: { type: 'string', description: 'the inputs, state or order that trigger it and the wrong result; for a quality finding, the cost and the existing file:line' },
  },
  required: ['title', 'severity', 'why', 'scenario'],
}

const INTENT = {
  type: 'object',
  properties: {
    sources: { type: 'array', items: { type: 'string' }, description: 'each source read: PR #n, issue #n, an ADR or plan path, the brief' },
    contract: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          id: { type: 'string', description: 'C1, C2, …' },
          behaviour: { type: 'string', description: 'one behaviour the change must have: inputs, states or orders it covers, and its failure handling' },
          source: { type: 'string' },
        },
        required: ['id', 'behaviour'],
      },
    },
    derived: { type: 'boolean', description: 'true when no source stated a contract and the items were worked out from the diff' },
    sanity: { type: 'array', items: ITEM, description: 'where the intended logic itself is unsound for the domain' },
    skills: { type: 'array', items: { type: 'string' }, description: 'the kit skills whose rules govern the surfaces the diff touches' },
    files: { type: 'number' },
    lines: { type: 'number', description: 'lines added plus removed' },
    paths: { type: 'array', items: { type: 'string' } },
    degraded: { type: 'string', description: 'a source you could not read, a tool that was absent' },
  },
  required: ['contract', 'derived', 'sanity', 'files', 'lines', 'paths'],
}

const CANDIDATES = {
  type: 'object',
  properties: {
    candidates: { type: 'array', items: ITEM },
    covered: { type: 'string', description: 'every changed path with what you checked on it, one clause each' },
    degraded: { type: 'string' },
  },
  required: ['candidates', 'covered'],
}

const VERDICTS = {
  type: 'object',
  properties: {
    verdicts: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          id: { type: 'string', description: 'the candidate, K<n>' },
          verdict: { type: 'string', description: 'CONFIRMED | PLAUSIBLE | REFUTED' },
          reason: { type: 'string', description: 'the line or lines that decided it, quoted with file:line' },
          severity: { type: 'string', description: 'blocker | major | minor, as you would assign it' },
          duplicateOf: { type: 'string', description: 'set only when this is the same defect as another candidate here: its id' },
        },
        required: ['id', 'verdict', 'reason'],
      },
    },
  },
  required: ['verdicts'],
}

const a = args || {}
const base = a.base ? String(a.base) : ''
const head = a.head ? String(a.head) : ''
const pr = a.pr ? String(a.pr).replace(/^#/, '') : ''
const contractText = a.contract ? String(a.contract) : ''
const project = a.project ? String(a.project) : ''
const projectModule = a.module ? String(a.module) : ''
const fork = projectModule === UPSTREAM
const mode = fork ? 'fork' : 'client'
const TIERS = Object.assign({ intent: 'fable', conformance: 'fable', domain: 'fable', find: 'opus', quality: 'sonnet', check: 'fable' }, a.tiers || {})
const FABLE_STAGES = ['intent', 'conformance', 'domain', 'check']
const maxChecks = Number.isInteger(a.maxChecks) && a.maxChecks > 0 ? a.maxChecks : 40
const proceed = a.proceed === true
const forkIndex = project ? `${project.replace(/\/+$/, '')}/docs/fork/README.md` : 'docs/fork/README.md'

const refuse = (error, detail) => {
  log(`refused: ${error}`)
  return { error, ...(detail || {}) }
}
if (!base || !head) return refuse('base and head are required', { expected: '{base, head, pr?, contract?, project?, module?, tiers?, maxChecks?, proceed?}' })
const above = Object.entries(TIERS).filter(
  ([stage, m]) => /mythos|session/i.test(String(m)) || (/fable/i.test(String(m)) && !FABLE_STAGES.includes(stage)),
)
if (above.length) return refuse('tier above opus', { tiers: Object.fromEntries(above), allowed: 'fable for intent, conformance, domain and check; opus and lower, by name, elsewhere' })
if (!projectModule) log('no module given: whether this project is the bsc-geth fork is unchecked; the review uses the bot\'s angles')
log(`${mode} · ${base}..${head}${pr ? ` · PR #${pr}` : ''}${contractText ? ' · brief given' : ''}`)

const range = `\`git diff ${base}..${head}\` in ${project || 'the session\'s tree'}`
const modeLine = fork
  ? `the bsc-geth fork: module github.com/ethereum/go-ethereum; its docs index, ${forkIndex}, names the rebase landmines document`
  : 'prediction-bot: a go-ethereum API resolves to the pinned bsc-geth fork, checked with `bsc-fork show <Symbol>`'
const seats = { intent: 0, find: 0, check: 0 }

// Intent. The contract before any code, and whether that logic is sound.
phase('Intent')
const sourcesLine = pr
  ? `pull request #${pr}: \`gh pr view ${pr} --json title,body,closingIssuesReferences\`, every issue it closes or names (\`gh issue view <n>\`), and every ADR, plan or brief its body names${contractText ? ', and the brief below' : ''}`
  : contractText
    ? 'the brief below, and every issue, ADR or plan it names'
    : 'none was given: look for one (the commit messages of the range, an issue or ADR they name) before deciding there is none'
seats.intent += 1
const intent = await agent(
  `You are the intent seat of a review of ${range} (${modeLine}).\n\n` +
    `1. **The contract, before any code.** Gather what this change was written to do. Sources: ${sourcesLine}. ` +
    `Write it as numbered items, C1, C2, …: each one behaviour the change must have, with the inputs, states or orders ` +
    `it covers and its failure handling, and the source it came from. A source's claim that something is verified, ` +
    `tested or covered is its author's belief: carry the behaviour, not the claim. When no source states a contract, ` +
    `set derived=true and write the items from the diff; the finders will know they are then checking the code against itself.\n` +
    `2. **Is that logic sound?** Before comparing any code, judge the contract against the domain. Load ` +
    `\`blockchain-kit:using-blockchain-kit\` with the Skill tool, then the skills its table names for the surfaces ` +
    `the diff touches, and read the rule homes they cite. Look for a state, input or order the contract does not ` +
    `handle (a reorg, a missed or cancelled round, a restart midway, a duplicate or late event, an empty or partial ` +
    `input, a boundary value), an item that contradicts a domain rule or another item, failure handling that loses ` +
    `data or hides an error, and a recovery path that cannot run. Each is a sanity finding with the scenario that ` +
    `breaks it; it cites code only where the code is where the unsound choice shows.\n` +
    `3. **The size.** \`git diff --shortstat ${base}..${head}\` for files and lines (added plus removed), and ` +
    `\`git diff --name-only ${base}..${head}\` for the paths.\n\n` +
    `Return the sources, the contract items, derived, the sanity findings, the skills you loaded, files, lines, ` +
    `paths, and degraded.` +
    (contractText ? `\n\n## The brief\n\n${contractText}` : ''),
  { label: 'intent', phase: 'Intent', agentType: SEAT, model: TIERS.intent, effort: 'high', schema: INTENT },
)
if (!intent || !Array.isArray(intent.contract)) return { error: 'the intent seat returned nothing', mode, base, head, seats }
const contract = intent.contract.filter((c) => c && c.id && c.behaviour)
const lines = Number(intent.lines) || 0
log(`contract: ${contract.length} item(s)${intent.derived ? ', derived from the diff' : ''} · ${(intent.sanity || []).length} sanity finding(s) · ${intent.files} file(s), ${lines} line(s)`)

// The pause (operator, 2026-10-23): every later seat is measured against this contract, so
// when it is in doubt the run stops here and the user decides before the finders spend.
// In doubt: no source stated it, or the intent seat judged its logic broken (a blocker).
// `proceed: true` goes on; resumed from this run, the intent seat is not paid for twice.
const doubts = [
  ...(intent.derived || contract.length === 0 ? ['no source stated the contract: it was worked out from the diff'] : []),
  ...(intent.sanity || []).filter((x) => x && x.severity === 'blocker').map((x) => `the logic itself: ${x.title}`),
]
if (doubts.length && !proceed) {
  log(`paused after Intent: ${doubts.join('; ')}`)
  return {
    paused: true,
    why: doubts,
    mode,
    base,
    head,
    pr: pr || null,
    contract: { sources: intent.sources || [], items: contract, derived: Boolean(intent.derived) },
    sanity: intent.sanity || [],
    size: { files: intent.files, lines },
    seats,
    next:
      'Show the user the contract, why the run paused and the sanity findings (unchecked). To go on: the same ' +
      'args plus proceed: true, resumed from this run. To correct the contract: the same args with contract set ' +
      'to the corrected text.',
  }
}

// Find. The angles, by mode; fewer finders than angles merges them.
const ANGLES = {
  conformance: `**Contract against code, both ways.** For each contract item: the code that does it (\`file:line\`), ` +
    `and whether it does so on every input, state and order the item covers. An item with no code behind it is a ` +
    `candidate. For each changed function and branch: the item it serves. Code that serves none is a change nobody ` +
    `asked for, a candidate unless it is plumbing an item needs.`,
  lines: `**Line by line, and what was removed.** Every hunk and its enclosing function: what input, state, timing or ` +
    `platform makes this line wrong (an inverted or wrong condition, an off-by-one, a nil dereference, a zero value ` +
    `taken as absent, the wrong variable, an error swallowed). Every deleted or replaced line: the behaviour it ` +
    `enforced, and where the new code re-establishes it; a removed guard, a dropped error path or a narrowed check ` +
    `with no replacement is a candidate.`,
  tracer: `**Callers, callees and Go's pitfalls.** For each changed function, its callers through ` +
    `\`go_symbol_references\`: a new precondition, a changed return shape, a new error value, an ordering ` +
    `dependency; for an interface, every implementation. Then: a goroutine with no exit path, a send on a closed ` +
    `channel, a struct holding a mutex or an atomic copied by value, a lock released before the state it guards is ` +
    `read, \`atomic.Value\` storing a second concrete type, a nil-map write, slice aliasing after \`append\`, map ` +
    `order relied on, \`defer\` in a loop, \`%w\` dropped so \`errors.Is\` stops matching, an error shadowed by ` +
    `\`:=\`, an unchecked type assertion, a timer, ticker, context or subscription never released. A captured loop ` +
    `variable is not a candidate (per-iteration since Go 1.22).`,
  domain: fork
    ? `**The fork's rules.** The Ext convention (\`blockchain-kit:fork-ext-convention\`): every fork-added durable ` +
      `surface ends in \`Ext\` and lives in a \`*_ext.go\` file, and upstream provenance is settled by \`git show ` +
      `<upstream-tag>:<path>\`, never by the suffix, where <upstream-tag> is the tag the fork's development document ` +
      `(through ${forkIndex}) names as its base. Rebase cost: an edit that deletes or restructures upstream lines, or ` +
      `touches a declaration the landmines document names (${forkIndex} lists it), is a candidate.`
    : `**The project's invariants.** Read each rule's home before judging it. Determinism and replay parity ` +
      `(\`internal/{replay,trigger,strategy,state}\` and what they call; \`docs/discipline.md\` rules 6, 12, 14, 15, ` +
      `32; \`docs/design-notes.md\` §3.10). The record spine and the stored-data contract (\`internal/{event,` +
      `eventlog,recorder}\`, the envelope, a version table, a golden; rules 3, 4, 5, 35, 37). Import boundaries (a ` +
      `new import between \`internal/\` packages; \`docs/architecture.md\` §3). Hot-path blocking and bounded ` +
      `allocation (\`internal/{feeds,state,trigger,strategy,executor}\` and their \`bot\` wiring; rules 16, 17, 40, ` +
      `41). A surface the diff does not touch gets one clause in \`covered\` saying so.`,
  tests: `**Tests, by reading.** A test is owed per invariant the contract names, not per item. For each test the ` +
    `diff adds or changes: the change to the code that would leave it green; a test no plausible defect turns red ` +
    `is a candidate (never run a mutant to find out). \`-count=1\` absent from a parity or determinism test command ` +
    `is a candidate.` +
    (fork ? '' : ` Template breadth is a minor candidate (\`docs/discipline.md\` rule 47): one test per row, counter, ` +
      `arm or field where one table-driven test covers the shape; a test asserting a count the next legitimate ` +
      `change must edit; a test the change made dead and left in place.`),
  quality: `**Quality.** Each cites what already exists by \`file:line\`, or names the simpler form: logic duplicated ` +
    `from an existing helper; state derivable from what is already held; needless complexity or dead code left ` +
    `behind; wasted work (repeated I/O, sequential independent calls, blocking work added to a hot or startup path); ` +
    `a special case layered on shared code where the mechanism should have generalized (in the fork, a branch in an ` +
    `upstream path instead of an \`Ext\` hook); and a rule of a governing \`CLAUDE.md\`, quoted, that a line breaks.`,
}
// The conformance and domain finders are their own seats at every size, at their own tiers;
// the other four angles share the rest, merged when there are fewer than four.
const GROUPS = {
  2: [['domain'], ['lines', 'tracer', 'tests', 'quality']],
  3: [['domain'], ['lines', 'tracer'], ['tests', 'quality']],
  4: [['domain'], ['lines'], ['tracer'], ['tests', 'quality']],
  5: [['domain'], ['lines'], ['tracer'], ['tests'], ['quality']],
}
const budget = Math.min(5, Math.max(2, Math.ceil(lines / 150)))
const groups = [['conformance'], ...GROUPS[budget]]
const tierOf = (group) => (group.length === 1 && group[0] in TIERS ? TIERS[group[0]] : TIERS.find)
// The skills every finder and checker loads: `go` and, in the fork, the Ext convention,
// whatever the intent seat named, then the ones it named for the touched surfaces.
const skills = [
  ...new Set([
    'blockchain-kit:go',
    ...(fork ? ['blockchain-kit:fork-ext-convention'] : []),
    ...(intent.skills || []).map((s) => String(s)).filter(Boolean),
  ]),
]
const loadLine = `Load with the Skill tool before judging: ${skills.join(', ')}.`
const contractBlock = contract.length
  ? contract.map((c) => `${c.id}. ${c.behaviour}`).join('\n')
  : '(no items: the intent seat found nothing the change was written to do)'
const sanityBlock = (intent.sanity || []).length
  ? `\n\nThe intent seat already raised these about the logic itself; do not raise them again:\n` +
    intent.sanity.map((s) => `- ${s.title}`).join('\n')
  : ''

phase('Find')
log(`${groups.length} finder(s): ${groups.map((g) => `${g.join('+')}@${tierOf(g)}`).join(' · ')}`)
const found = await parallel(
  groups.map((group) => () => {
    seats.find += 1
    return agent(
      `You are a finder in a review of ${range} (${modeLine}). Read every changed file at ${head} whole, not only ` +
        `its hunks, and the enclosing function of each hunk.\n\n` +
        `The contract this change was written against` +
        (intent.derived ? ' (worked out from the diff, since no source stated one: a hypothesis, not a spec)' : '') +
        `:\n${contractBlock}${sanityBlock}\n\n` +
        `${loadLine}\n\n` +
        `Your angle${group.length > 1 ? 's' : ''}:\n\n${group.map((k) => ANGLES[k]).join('\n\n')}\n\n` +
        `Surface up to 8 candidates per angle, each with file, the line at ${head}, title, the contract item it ` +
        `concerns (C<n>, or none), severity as you see it, why, and scenario. Pass through every candidate with a ` +
        `nameable scenario: a checker verifies each one independently, and a finder that drops a half-believed ` +
        `candidate is the commonest cause of a miss. Two angles flagging one line for different reasons are two ` +
        `candidates. Return covered: every changed path with what you checked on it.`,
      { label: `find:${group.join('+')}`, phase: 'Find', agentType: SEAT, model: tierOf(group), effort: 'high', schema: CANDIDATES },
    )
  }),
)
const coverage = groups.map((group, i) =>
  found[i]
    ? { angles: group, covered: found[i].covered || '', degraded: found[i].degraded || '' }
    : { angles: group, covered: '', degraded: 'the finder returned nothing: these angles were not covered' },
)

// Candidates: the sanity findings, then the finders'. None is merged here: two candidates
// on one line may be two defects, and only a reader can tell; the checker marks duplicates.
const pool = []
for (const s of intent.sanity || []) if (s && s.title) pool.push({ ...s, angle: 'intent' })
found.forEach((f, i) =>
  (f && Array.isArray(f.candidates) ? f.candidates : []).forEach((c) => {
    if (c && c.title) pool.push({ ...c, angle: groups[i].join('+') })
  }),
)
pool.sort((x, y) => (SEVERITY[x.severity] ?? 3) - (SEVERITY[y.severity] ?? 3))
pool.forEach((c, i) => (c.id = `K${i + 1}`))
const toCheck = pool.slice(0, maxChecks)
const unchecked = pool.slice(maxChecks).map((c) => ({ ...c, reason: 'over maxChecks' }))
log(`${pool.length} candidate(s)${unchecked.length ? `, ${unchecked.length} over maxChecks left unchecked` : ''}`)

// Check. One seat per changed file reads it once and decides each candidate in it; it
// raised none of them. A file with more than eight is split; the contract's own go together.
const PER_CHECKER = 8
const byFile = new Map()
for (const c of toCheck) {
  const key = c.file || ''
  if (!byFile.has(key)) byFile.set(key, [])
  byFile.get(key).push(c)
}
const batches = []
for (const [file, list] of byFile) {
  list.sort((x, y) => (Number(x.line) || 0) - (Number(y.line) || 0))
  const parts = Math.ceil(list.length / PER_CHECKER)
  for (let k = 0; k < parts; k++) {
    batches.push({
      file,
      list: list.slice(k * PER_CHECKER, (k + 1) * PER_CHECKER),
      label: `check:${file || 'contract'}${parts > 1 ? `#${k + 1}` : ''}`,
    })
  }
}
phase('Check')
const itemText = (id) => {
  const hit = contract.find((c) => c.id === id)
  return hit ? `${hit.id}. ${hit.behaviour}` : 'none'
}
const describe = (c) =>
  `${c.id}. ${c.title}\n  Where: ${c.file ? `${c.file}:${c.line ?? '?'}` : '(the contract, no line)'} · angle: ${c.angle}\n` +
  `  Contract item: ${itemText(c.item)}\n  Why: ${c.why}\n  Scenario: ${c.scenario}`
const answers = await parallel(
  batches.map((b) => () => {
    seats.check += 1
    return agent(
      `You are a checker in a review of ${range} (${modeLine}). By reading only. ${loadLine}\n\n` +
        (b.file
          ? `Finders raised these candidates in ${b.file}. Read the file at ${head} whole once, and what it calls or is ` +
            `called by as each candidate needs, then decide each one on its own.\n\n`
          : `The intent seat raised these about the contract's logic itself. Read what each needs, then decide each ` +
            `one on its own.\n\n`) +
        `${b.list.map(describe).join('\n\n')}\n\n` +
        `You raised none of these. Catch every real defect: a missed one ships. One verdict per id:\n` +
        `- CONFIRMED: you can name the inputs or state that trigger it and the wrong result. Quote the line.\n` +
        `- PLAUSIBLE: the mechanism is real and the trigger depends on timing, configuration or environment that is ` +
        `realistic here (an interleaving, a restart, a cold cache, an error path, a reachable nil, a boundary the code ` +
        `does not exclude). Say what would confirm it.\n` +
        `- REFUTED: only when the code shows it: it does not say that (quote it); a type, constant or invariant makes ` +
        `it impossible (show it); this diff already handles it (cite the guard); the diff neither moved nor ` +
        `re-exposed it; or it has no observable effect. A quality candidate is refuted when the cited helper or state ` +
        `does not exist or does not do what the diff re-does.\n` +
        `Two candidates that are the same defect (one mechanism, one trigger): decide the clearer one, and give the ` +
        `other its id in duplicateOf. Two defects on one line are two verdicts. Give each reason with file:line, and ` +
        `the severity you would assign.`,
      { label: b.label, phase: 'Check', agentType: SEAT, model: TIERS.check, effort: 'high', schema: VERDICTS },
    )
  }),
)

const verdictOf = new Map()
batches.forEach((b, i) => {
  const ids = new Set(b.list.map((c) => c.id))
  const got = answers[i] && Array.isArray(answers[i].verdicts) ? answers[i].verdicts : []
  for (const v of got) if (v && ids.has(String(v.id))) verdictOf.set(String(v.id), v)
})
const byId = new Map(toCheck.map((c) => [c.id, c]))
const findings = []
const refuted = []
const merged = []
const kept = new Map()
for (const c of toCheck) {
  const v = verdictOf.get(c.id)
  const word = v && typeof v.verdict === 'string' ? v.verdict.toUpperCase() : ''
  const into = v && v.duplicateOf ? String(v.duplicateOf) : ''
  if (into && into !== c.id && byId.has(into) && verdictOf.has(into) && (byId.get(into).file || '') === (c.file || '')) {
    merged.push({ id: c.id, title: c.title, into, angle: c.angle })
    continue
  }
  const out = {
    id: c.id,
    title: c.title,
    file: c.file || '',
    line: c.line ?? null,
    severity: v && v.severity in SEVERITY ? v.severity : c.severity,
    item: c.item || 'none',
    angles: [c.angle],
    why: c.why,
    scenario: c.scenario,
    verdict: word || 'UNCHECKED',
    reason: v ? v.reason : 'the checker returned no verdict for it',
  }
  if (word === 'REFUTED') refuted.push(out)
  else if (word === 'CONFIRMED' || word === 'PLAUSIBLE') {
    findings.push(out)
    kept.set(c.id, out)
  } else unchecked.push({ ...c, reason: out.reason })
}
// A duplicate's angle joins the finding it was merged into, when that one stands.
for (const m of merged) {
  const target = kept.get(m.into)
  if (target && !target.angles.includes(m.angle)) target.angles.push(m.angle)
}
const rank = (f) => (SEVERITY[f.severity] ?? 3) * 2 + (f.verdict === 'CONFIRMED' ? 0 : 1)
findings.sort((x, y) => rank(x) - rank(y))
findings.forEach((f, i) => (f.n = i + 1))
log(`${findings.length} finding(s) stand · ${refuted.length} refuted · ${merged.length} merged · ${unchecked.length} unchecked · seats ${seats.intent}+${seats.find}+${seats.check}`)

return {
  mode,
  base,
  head,
  pr: pr || null,
  contract: { sources: intent.sources || [], items: contract, derived: Boolean(intent.derived) },
  findings,
  refuted,
  merged,
  unchecked,
  coverage,
  size: { files: intent.files, lines },
  seats,
  degraded: [intent.degraded, ...coverage.map((c) => c.degraded)].filter(Boolean),
}
