// Runs a kit workflow against scripted agents, for tests/test_implement.py and
// tests/test_review.py.
//
// The Workflow tool gives a script `args`, `agent`, `parallel`, `pipeline`, `log`
// and `phase`. Here `agent` answers from a scenario instead of a model, so the
// script's own decisions (what it refuses, merges, skips and reports) are
// observable without a session. What a real agent does with a prompt is a live run.
//
// Usage: node tests/implement_harness.mjs <scenario.json>
//   scenario: { workflow?, args, answers: { "<label>": <value> | null | {"__throw": "msg"} } }
//   workflow names the script under workflows/ (default implement). A label is the agent
//   call's opts.label: lane:<id>, integrate, gate, review, fix, re-gate in implement;
//   intent, find:<angles>, check:<n> in review. A label with no answer returns null (a
//   dead stage).
// Output: one JSON object { result, calls: [{label, model, agentType, isolation,
//   prompt, phase}], logs: [], phases: [] } on stdout.
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const scenario = JSON.parse(readFileSync(process.argv[2], 'utf8'))
const workflow = scenario.workflow || 'implement'
const source = readFileSync(join(here, '..', 'workflows', `${workflow}.js`), 'utf8').replace('export const meta', 'const meta')

const calls = []
const logs = []
const agent = async (prompt, opts = {}) => {
  calls.push({ label: opts.label, model: opts.model ?? null, agentType: opts.agentType ?? null, isolation: opts.isolation ?? null, phase: opts.phase ?? null, prompt })
  const answer = (scenario.answers || {})[opts.label]
  if (answer && answer.__throw) throw new Error(answer.__throw)
  return answer === undefined ? null : answer
}
const settle = async (thunk) => {
  try {
    return await thunk()
  } catch {
    return null
  }
}
const parallel = (thunks) => Promise.all(thunks.map(settle))
const pipeline = () => {
  throw new Error(`${workflow}.js does not use pipeline()`)
}

const AsyncFunction = Object.getPrototypeOf(async () => {}).constructor
const run = new AsyncFunction('args', 'agent', 'parallel', 'pipeline', 'log', 'phase', source)
const phases = []
const result = await run(scenario.args, agent, parallel, pipeline, (m) => logs.push(String(m)), (t) => phases.push(t))
process.stdout.write(JSON.stringify({ result, calls, logs, phases }))
