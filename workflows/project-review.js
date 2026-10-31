export const meta = {
  name: 'project-review',
  description: 'Whole-project intent-first review at one commit: the contract and the measured numbers from the docs, whether that logic is sound, finders by angle, one independent checker per file with candidates.',
  whenToUse:
    'A whole repository reviewed at one commit against its own docs, when the user asks. Not for a pull request or a branch: that is the review workflow.',
  phases: [
    { title: 'Intent', detail: 'one seat: the project contract from its docs, the measured numbers, whether the logic is sound, the areas to review', model: 'fable' },
    { title: 'Find', detail: 'conformance, domain and numbers at fable; lines (two seats), tracer and tests at opus; quality at sonnet', model: 'fable' },
    { title: 'Check', detail: 'one independent checker per file with candidates, a verdict for each, by reading', model: 'fable' },
  ],
}

// There is no diff: the tree at `head` is the subject, and the project's own docs are the
// contract. Intent first: the intent seat writes down what the system must do and what it has
// measured before any code is compared, and judges whether that logic is sound; finders then
// work against that contract by angle; a checker that raised none of the candidates decides
// each one by reading.
//
// This script holds the method. What is true of one repository (which docs to read, which
// packages are the money path, where each rule's home is, what the numbers' units are) is in
// that repository's review guide, a document every seat reads: `guide` below, and
// commands/project-review.md says what the guide must hold.
//
// Tiers: fable wherever a wrong judgment misdirects or silently drops something downstream
// (the contract and the numbers, the mapping of code to intent, the project's invariants, and
// every checker's verdict); opus for the pattern angles; sonnet for quality, whose candidates
// are search-and-cite and are checked afterwards anyway.
//
// Invoke with args (the Workflow tool's `args`, as JSON, not a string):
//   {
//     project: '/abs/checkout',   // required: filled with `module` by hooks/implement-args
//     head: '<sha>',              // required: git rev-parse HEAD; the tree is at it
//     guide: 'docs/project-review.md', // required: the repository's review guide, repo-relative
//     module: 'example.com/bot',  // the module line of go.mod (informational)
//     maxChecks: 48,              // the most candidates checked; the rest come back unchecked
//     perAngle: 10,               // candidates a finder may raise per angle
//     tiers: { intent, conformance, domain, numbers, lines, tracer, tests, quality, check },
//                                 // any seat by name; mythos and the session tier are refused
//   }
// Return: the contract as read, the numbers table, the sanity findings, the findings that
// stand with their verdicts, the refuted, the merged duplicates, the unchecked, the coverage
// per angle, the seats spent, and what was degraded. Nothing is edited, built, run or posted.

const SEAT = 'blockchain-kit:review-seat'
const SEVERITY = { blocker: 0, major: 1, minor: 2 }
const RANK = { haiku: 0, sonnet: 1, opus: 2, fable: 3 }

const ITEM = {
  type: 'object',
  properties: {
    title: { type: 'string' },
    file: { type: 'string', description: 'repo-relative; empty when the finding is about the contract or a doc alone' },
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
    sources: { type: 'array', items: { type: 'string' }, description: 'each doc read, with how much of it' },
    contract: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          id: { type: 'string', description: 'C1, C2, …' },
          behaviour: { type: 'string', description: 'one behaviour the system must have: inputs, states or orders it covers, and its failure handling' },
          source: { type: 'string', description: 'path:line or path §section; "derived" when no doc states it' },
        },
        required: ['id', 'behaviour', 'source'],
      },
    },
    numbers: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          quantity: { type: 'string' },
          documented: { type: 'string', description: 'the value a doc or spec gives' },
          where: { type: 'string', description: 'path:line of the documented value' },
          status: { type: 'string', description: 'measured | shadow | UNRUN | not measured | disputed' },
          measured: { type: 'string', description: 'the measured value, or what the status means here' },
          whereMeasured: { type: 'string' },
          note: { type: 'string', description: 'a disagreement between sources, or a code pointer that gives a different value' },
        },
        required: ['quantity', 'documented', 'where', 'status'],
      },
    },
    sanity: { type: 'array', items: ITEM, description: 'where the intended logic itself is unsound for the domain' },
    areas: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          name: { type: 'string' },
          paths: { type: 'array', items: { type: 'string' }, description: 'repo-relative packages or files' },
          items: { type: 'array', items: { type: 'string' }, description: 'the contract items this area implements' },
          why: { type: 'string', description: 'why it ranks where it does' },
        },
        required: ['name', 'paths', 'items'],
      },
      description: 'most consequential first',
    },
    ruleHomes: { type: 'array', items: { type: 'string' }, description: 'doc locations a finder cites for a determinism, record-spine, boundary, hot-path or test-breadth rule' },
    skills: { type: 'array', items: { type: 'string' }, description: 'the kit skills whose rules govern the surfaces the areas touch' },
    degraded: { type: 'string', description: 'a source you could not read, a tool that was absent' },
  },
  required: ['contract', 'numbers', 'sanity', 'areas'],
}

const CANDIDATES = {
  type: 'object',
  properties: {
    candidates: { type: 'array', items: ITEM },
    covered: { type: 'string', description: 'every area path with what you checked on it, one clause each' },
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
const project = a.project ? String(a.project).replace(/\/+$/, '') : ''
const head = a.head ? String(a.head) : ''
const guide = a.guide ? String(a.guide) : ''
const projectModule = a.module ? String(a.module) : ''
const maxChecks = Number.isInteger(a.maxChecks) && a.maxChecks > 0 ? a.maxChecks : 48
const perAngle = Number.isInteger(a.perAngle) && a.perAngle > 0 ? a.perAngle : 10
const SEATS = { intent: 'fable', conformance: 'fable', domain: 'fable', numbers: 'fable', lines: 'opus', tracer: 'opus', tests: 'opus', quality: 'sonnet', check: 'fable' }
const TIERS = Object.assign({}, SEATS, a.tiers || {})

const refuse = (error, detail) => {
  log(`refused: ${error}`)
  return { error, ...(detail || {}) }
}
if (!project || !head || !guide) return refuse('project, head and guide are required', { expected: '{project, head, guide, module?, maxChecks?, perAngle?, tiers?}' })
const above = Object.entries(TIERS).filter(([seat, m]) => !Object.hasOwn(SEATS, seat) || !Object.hasOwn(RANK, String(m)))
if (above.length) return refuse('tier not allowed', { tiers: Object.fromEntries(above), allowed: `${Object.keys(SEATS).join(', ')}: haiku, sonnet, opus or fable, by name` })
log(`project review · ${project} @ ${head} · guide ${guide}${projectModule ? ` · ${projectModule}` : ''}`)

const limits =
  `You READ ONLY: no git write verb, no file write, no build, no test, no make target, no go mod, no formatter, ` +
  `no redirect into the tree, no GitHub write, no mutant. You consult nobody and dispatch nobody; uncertainty goes ` +
  `into your return with its basis stated. Every claim names its basis: a file:line at ${head}, or a command you ran ` +
  `and what it printed. Read excerpts (sed -n, rg), not dumps of large files; no raw logs in your return. This is a ` +
  `whole-project review: there is no diff, and every line under the paths named is in scope.`
const seats = { intent: 0, find: 0, check: 0 }

// Intent. The contract and the numbers before any code, and whether that logic is sound.
phase('Intent')
seats.intent += 1
const intent = await agent(
  `You are the INTENT SEAT of a whole-project review of the checkout at ${project}, tree at ${head}. ${limits}\n\n` +
    `Your job is to write down, BEFORE any code is compared, what this project was written to do, what it has ` +
    `measured, and whether that intended logic is sound. Finders will check the code against your contract and ` +
    `checkers will verify every candidate; a wrong or missing item here misdirects everything after you.\n\n` +
    `Read the review guide first, whole: ${project}/${guide}. It names the sources to read and their order, what the ` +
    `contract must cover, the numbers to collect, the domain the logic is judged against, and how to choose the ` +
    `areas. If you cannot read it, return an empty contract and say so in degraded. Read the sources it names, then ` +
    `load \`blockchain-kit:using-blockchain-kit\` with the Skill tool, the skills its table names for the surfaces you ` +
    `will name as areas, and the rule homes they cite.\n\n` +
    `A source's claim that something is verified, tested, measured or covered is its author's belief: carry the ` +
    `behaviour, not the claim. Where two docs disagree, record both with path:line.\n\n` +
    `Return:\n` +
    `- contract: 25 to 45 items C1, C2, …, one behaviour each with the inputs, states or orders it covers and its ` +
    `failure handling, and its source. Cover everything the guide says the contract must cover. Mark source "derived" ` +
    `when no doc states an item and you inferred it.\n` +
    `- numbers: every number the guide says to collect, each with where it is documented, its status (measured, ` +
    `shadow, UNRUN, not measured, disputed), where it is measured, and a note when a doc or a code pointer gives a ` +
    `different value.\n` +
    `- sanity: where the INTENDED logic itself is unsound for the domain the guide describes. Each with severity ` +
    `(blocker: a wrong result, money or data lost, a broken invariant; major: a real trigger the gates do not catch; ` +
    `minor: anything else), why, the scenario that breaks it, the item(s) it concerns. Cite code only where the code ` +
    `is where the unsound choice shows. Skip what the project's own open-questions or defects docs already list ` +
    `unless you judge it worse than the doc says; then say so.\n` +
    `- areas: 5 to 8 review areas, most consequential first, chosen as the guide says, each with its repo-relative ` +
    `paths, the contract items it implements and why it ranks there.\n` +
    `- ruleHomes, skills, sources, degraded.`,
  { label: 'intent', phase: 'Intent', agentType: SEAT, model: TIERS.intent, effort: 'high', schema: INTENT },
)
if (!intent || !Array.isArray(intent.contract)) return { error: 'the intent seat returned nothing', project, head, seats }
const contract = intent.contract.filter((c) => c && c.id && c.behaviour)
const numbers = Array.isArray(intent.numbers) ? intent.numbers.filter((n) => n && n.quantity) : []
const sanity = Array.isArray(intent.sanity) ? intent.sanity.filter((s) => s && s.title) : []
const areas = (Array.isArray(intent.areas) ? intent.areas : []).filter((x) => x && x.name && Array.isArray(x.paths) && x.paths.length)
if (!contract.length) return { error: 'the intent seat found no contract in the docs', project, head, intent, seats }
if (!areas.length) return { error: 'the intent seat named no areas to review', project, head, intent, seats }
log(`contract: ${contract.length} item(s) · ${numbers.length} number(s) · ${sanity.length} sanity finding(s) · ${areas.length} area(s)`)

// Find. Each angle a seat; lines is split over two halves of the areas.
const half = Math.ceil(areas.length / 2)
const ANGLES = {
  conformance: {
    tier: TIERS.conformance,
    areas,
    text:
      `**Contract against code, both ways.** For each contract item: the code that does it (file:line), and whether it ` +
      `does so on every input, state and order the item covers. An item with no code behind it is a candidate. For each ` +
      `exported function and each branch on the money path and the record spine: the item it serves. Code there that ` +
      `serves none is a candidate unless it is plumbing an item needs. A doc that describes behaviour the code no longer ` +
      `has is a candidate against the doc (file is the doc path).`,
  },
  domain: {
    tier: TIERS.domain,
    areas,
    text:
      `**The project's invariants.** The review guide lists them, each with its surface and its rule's home. Read each ` +
      `home before judging it, then check every surface the guide names. A surface you found clean gets one clause in ` +
      `covered saying so.`,
  },
  numbers: {
    tier: TIERS.numbers,
    areas,
    text:
      `**Numbers against intent and evidence.** For every threshold, limit, fee, timing constant and fixed-point ` +
      `conversion on the surfaces the review guide names: the value in code (file:line), the value the docs or specs ` +
      `give (the numbers table below), and whether the two agree in value, unit and scale (the guide names the units ` +
      `that matter here). A value the code treats as established but the numbers table marks UNRUN, shadow or not ` +
      `measured is a candidate (the scenario names what the code would do if the measurement came out the other way). ` +
      `A truncation that drops a unit, a threshold compared with the wrong inclusivity, and each number-handling ` +
      `mistake the guide lists are candidates. Every row of the numbers table ` +
      `gets a clause in covered: agrees, disagrees, or no code reads it.`,
  },
  linesA: {
    tier: TIERS.lines,
    areas: areas.slice(0, half),
    text:
      `**Line by line.** Read every non-test Go file in your areas whole. For each function: what input, state, timing ` +
      `or platform makes a line wrong (an inverted or wrong condition, an off-by-one, a nil dereference, a zero value ` +
      `taken as absent, the wrong variable, an error swallowed or logged and carried on, a shadowed := that drops an ` +
      `assignment, an unchecked type assertion, integer overflow or sign on an amount, a comparison across units). ` +
      `A guard that a comment says exists but the code lacks is a candidate.`,
  },
  linesB: {
    tier: TIERS.lines,
    areas: areas.slice(half),
    text:
      `**Line by line.** Read every non-test Go file in your areas whole. For each function: what input, state, timing ` +
      `or platform makes a line wrong (an inverted or wrong condition, an off-by-one, a nil dereference, a zero value ` +
      `taken as absent, the wrong variable, an error swallowed or logged and carried on, a shadowed := that drops an ` +
      `assignment, an unchecked type assertion, integer overflow or sign on an amount, a comparison across units). ` +
      `A guard that a comment says exists but the code lacks is a candidate.`,
  },
  tracer: {
    tier: TIERS.tracer,
    areas,
    text:
      `**Callers, callees and Go's pitfalls.** For each exported function and each goroutine on the surfaces the ` +
      `review guide names for this angle: its callers through go_symbol_references (rg when gopls is absent: say so), a ` +
      `precondition a caller does not meet, a return value a caller ignores, an error value a caller cannot ` +
      `distinguish, an ordering dependency between two callers; for an interface, every implementation and whether ` +
      `each meets the contract the callers assume. Then: a goroutine with no exit path, a send on a closed or ` +
      `unbuffered channel under a lock, a context never cancelled, a timer or ticker or subscription never released, ` +
      `a mutex held across a blocking call, a shared map or slice written from two goroutines, a once-only action ` +
      `that two paths can reach. A captured loop variable is not a candidate.`,
  },
  tests: {
    tier: TIERS.tests,
    areas,
    text:
      `**Tests, by reading.** A test is owed per invariant the contract names. On the surfaces the review guide names ` +
      `for this angle: which test protects each item, and the change to the code that would leave it green; a test no ` +
      `plausible defect turns red is a candidate (never run a mutant to find out). A determinism test command without ` +
      `-count=1, a fixture-dependent test that passes when the fixture is missing, and a skip whose condition is always ` +
      `true are candidates, with the test rules the guide names. An item with no test behind it is a candidate with ` +
      `the item named.`,
  },
  quality: {
    tier: TIERS.quality,
    areas,
    text:
      `**Quality.** Each candidate cites what already exists by file:line, or names the simpler form: logic duplicated ` +
      `from an existing helper; state derivable from what is already held; needless complexity or dead code; wasted ` +
      `work (repeated I/O, sequential independent calls, blocking work on a hot or startup path); a special case ` +
      `layered on shared code where the mechanism should have generalized; and a rule of CLAUDE.md or ` +
      `the rule document the review guide names, quoted, that a line breaks. A preference is not a finding.`,
  },
}
const angleNames = Object.keys(ANGLES).filter((k) => ANGLES[k].areas.length)
const skills = [...new Set(['blockchain-kit:go', ...(intent.skills || []).map((s) => String(s)).filter(Boolean)])]
const loadLine = `Load with the Skill tool before judging: ${skills.join(', ')}.`
const contractBlock = contract.map((c) => `${c.id}. ${c.behaviour} [${c.source || 'derived'}]`).join('\n')
const numbersBlock = numbers.length
  ? numbers.map((n) => `- ${n.quantity}: documented ${n.documented} (${n.where}); ${n.status}${n.measured ? `: ${n.measured}` : ''}${n.whereMeasured ? ` (${n.whereMeasured})` : ''}${n.note ? ` — ${n.note}` : ''}`).join('\n')
  : '(the intent seat found no numbers)'
const sanityBlock = sanity.length
  ? `\n\nThe intent seat already raised these about the logic itself; do not raise them again:\n${sanity.map((s) => `- ${s.title}`).join('\n')}`
  : ''
const ruleHomes = (intent.ruleHomes || []).map((r) => `- ${r}`).join('\n') || '- the rule homes the review guide names'
const areaBlock = (list) => list.map((x, i) => `${i + 1}. ${x.name}: ${x.paths.join(', ')} — items ${(x.items || []).join(', ') || 'none named'}${x.why ? `; ${x.why}` : ''}`).join('\n')

phase('Find')
log(`${angleNames.length} finder(s): ${angleNames.map((k) => `${k}@${ANGLES[k].tier}`).join(' · ')}`)
const found = await parallel(
  angleNames.map((k) => () => {
    seats.find += 1
    const ang = ANGLES[k]
    return agent(
      `You are a finder in a whole-project review of the checkout at ${project}, tree at ${head}. ${limits}\n\n` +
        `Read the review guide first: ${project}/${guide}.\n\n` +
        `${loadLine}\n\n` +
        `The contract this system was written to (from its docs; the intent seat read them):\n${contractBlock}\n\n` +
        `The numbers the docs give and what is measured:\n${numbersBlock}\n\n` +
        `Rule homes to cite:\n${ruleHomes}${sanityBlock}\n\n` +
        `Your areas, most consequential first:\n${areaBlock(ang.areas)}\n\n` +
        `Your angle:\n\n${ang.text}\n\n` +
        `Surface up to ${perAngle} candidates, the most consequential first, each with file, the line at ${head}, title, ` +
        `the contract item it concerns (C<n>, or none), severity as you see it, why, and scenario. Pass through every ` +
        `candidate with a nameable scenario: a checker verifies each one independently, and a finder that drops a ` +
        `half-believed candidate is the commonest cause of a miss. Return covered: every area path with what you ` +
        `checked on it, and degraded: any tool you lacked (gopls) or path you did not reach.`,
      { label: `find:${k}`, phase: 'Find', agentType: SEAT, model: ang.tier, effort: 'high', schema: CANDIDATES },
    )
  }),
)
const coverage = angleNames.map((k, i) =>
  found[i]
    ? { angle: k, tier: ANGLES[k].tier, covered: found[i].covered || '', degraded: found[i].degraded || '' }
    : { angle: k, tier: ANGLES[k].tier, covered: '', degraded: 'the finder returned nothing: this angle was not covered' },
)

// Candidates: the sanity findings, then the finders'. None is merged here: two candidates on
// one line may be two defects, and only a reader can tell; the checker marks duplicates.
const pool = []
for (const s of sanity) pool.push({ ...s, angle: 'intent' })
found.forEach((f, i) =>
  (f && Array.isArray(f.candidates) ? f.candidates : []).forEach((c) => {
    if (c && c.title) pool.push({ ...c, angle: angleNames[i] })
  }),
)
pool.sort((x, y) => (SEVERITY[x.severity] ?? 3) - (SEVERITY[y.severity] ?? 3))
pool.forEach((c, i) => (c.id = `K${i + 1}`))
const toCheck = pool.slice(0, maxChecks)
const unchecked = pool.slice(maxChecks).map((c) => ({ ...c, reason: 'over maxChecks' }))
log(`${pool.length} candidate(s)${unchecked.length ? `, ${unchecked.length} over maxChecks left unchecked` : ''}`)

// Check. One seat per file reads it once and decides each candidate in it; it raised none of
// them. A file with more than eight is split; the contract's own go together.
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
    batches.push({ file, list: list.slice(k * PER_CHECKER, (k + 1) * PER_CHECKER), label: `check:${file || 'contract'}${parts > 1 ? `#${k + 1}` : ''}` })
  }
}
phase('Check')
const itemText = (id) => {
  const hit = contract.find((c) => c.id === id)
  return hit ? `${hit.id}. ${hit.behaviour}` : 'none'
}
const describe = (c) =>
  `${c.id}. ${c.title}\n  Where: ${c.file ? `${c.file}:${c.line ?? '?'}` : '(the contract or a doc, no line)'} · angle: ${c.angle}\n` +
  `  Contract item: ${itemText(c.item)}\n  Why: ${c.why}\n  Scenario: ${c.scenario}`
const answers = await parallel(
  batches.map((b) => () => {
    seats.check += 1
    return agent(
      `You are a checker in a whole-project review of the checkout at ${project}, tree at ${head}. ${limits} ${loadLine} ` +
        `The review guide, ${project}/${guide}, says what the project's rules and units are.\n\n` +
        (b.file
          ? `Finders raised these candidates in ${b.file}. Read the file at ${head} whole once, and what it calls or is ` +
            `called by as each candidate needs (go_symbol_references; rg when gopls is absent, and say so), then decide each one on its own.\n\n`
          : `The intent seat or a finder raised these about the project's logic or its docs, with no code line. Read what ` +
            `each needs, then decide each one on its own.\n\n`) +
        `${b.list.map(describe).join('\n\n')}\n\n` +
        `You raised none of these. Catch every real defect: a missed one ships, and a wrong refutal drops it silently. One verdict per id:\n` +
        `- CONFIRMED: you can name the inputs or state that trigger it and the wrong result. Quote the line.\n` +
        `- PLAUSIBLE: the mechanism is real and the trigger depends on timing, configuration or environment that is ` +
        `realistic here (an interleaving, a restart, a cold cache, an error path, a reachable nil, a boundary the code ` +
        `does not exclude). Say what would confirm it.\n` +
        `- REFUTED: only when the code shows it: it does not say that (quote it); a type, constant or invariant makes ` +
        `it impossible (show it); a guard elsewhere handles it (cite it); or it has no observable effect. A numbers ` +
        `candidate is refuted when code and doc agree once units and scale are read correctly (show the conversion). ` +
        `A quality candidate is refuted when the cited helper or state does not exist or does not do what the code re-does.\n` +
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
const stands = (v) => Boolean(v) && !v.duplicateOf && /^(CONFIRMED|PLAUSIBLE)$/i.test(String(v.verdict))
const findings = []
const refuted = []
const merged = []
const kept = new Map()
for (const c of toCheck) {
  const v = verdictOf.get(c.id)
  // A duplicate merges only into a finding that stands; otherwise its own verdict decides it.
  if (v && v.duplicateOf && v.duplicateOf !== c.id && stands(verdictOf.get(v.duplicateOf))) {
    merged.push({ id: c.id, title: c.title, into: v.duplicateOf, angle: c.angle })
    continue
  }
  const word = v && typeof v.verdict === 'string' ? v.verdict.toUpperCase() : ''
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
for (const m of merged) {
  const target = kept.get(m.into)
  if (target && !target.angles.includes(m.angle)) target.angles.push(m.angle)
}
const rank = (f) => (SEVERITY[f.severity] ?? 3) * 2 + (f.verdict === 'CONFIRMED' ? 0 : 1)
findings.sort((x, y) => rank(x) - rank(y))
findings.forEach((f, i) => (f.n = i + 1))
log(`${findings.length} finding(s) stand · ${refuted.length} refuted · ${merged.length} merged · ${unchecked.length} unchecked · seats ${seats.intent}+${seats.find}+${seats.check}`)

return {
  project,
  head,
  guide,
  module: projectModule || null,
  contract: { sources: intent.sources || [], items: contract },
  numbers,
  sanity,
  areas,
  findings,
  refuted,
  merged,
  unchecked,
  coverage,
  tiers: TIERS,
  seats,
  degraded: [intent.degraded, ...coverage.map((c) => c.degraded)].filter(Boolean),
}
