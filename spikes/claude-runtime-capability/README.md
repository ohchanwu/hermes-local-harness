# Minimal official Claude-runtime capability observation

2026-10-17 UTC; card `kanban://harness/t_178bbd7d`, implementation run45.
Baseline `4cf9c892383647efda613b91c6054eba94260faf`, protected ref
`refs/harness/baselines/t_178bbd7d`, isolated branch `wt/t_178bbd7d`.

Verdict: **PASS for this bounded serial capability observation**. An unmodified
Claude Code **2.1.283**, selecting exactly **claude-opus-5-5**, emitted a real
structured tool-use ID and complete arguments while a synthetic MCP invocation
was parked. The owning Hermes worker performed one actual native `read_file`,
returned its fixture content to that same invocation, and Claude continued with
the fixture value. A second pending invocation was cancelled without native
execution or result delivery. This supports considering a separately authorized
small serial provider; it is **not** a provider implementation, accepted full
role workflow, measured billing result, or rollout/readiness approval.

The two earlier offline generations remain PARTIAL/stopped, unchanged. This is
a different actual-runtime observation, not generation3 of those mocks. See the
[governing specification](../../docs/specs/261016-claude-max20x-model-portability.md),
[plan](../../docs/plans/261016-claude-max20x-implementation-plan.md), and
[historical generation2 evidence](../claude-subscription-feasibility/README.md).

## Small implementation and authority

[probe.py](probe.py) is one stdlib program with two explicit modes: the stdio MCP
server and its one-off serial observer. A bare invocation does nothing live.
There is no SDK, provider registration, Hermes import/core change, new dependency,
additional filesystem/shell executor, or live profile/configuration change.
Direct CLI print output alone cannot rendezvous with an external native tool;
this small script supplies the parked stdio-MCP mailbox and lifecycle observer.
It is not a general controller/framework.

The MCP tool schema has one required path, an enum containing only the owned
synthetic fixture, and no additional arguments. The MCP server **does not open
that path**. It publishes its real JSON-RPC request ID/name/arguments, waits for
one matching delivery, then returns that text. The parent observes the separate
model `tool_use` ID/name/arguments in real stream events and the assistant
snapshot. Only a single outstanding invocation is allowed. Repeated snapshots
of the same invocation are not another execution; distinct/duplicate calls,
mismatched results, replay and stale cancellation are rejected.

The actual Hermes executor here is the **parent harness-worker conversation's
`functions.read_file` tool**, not a Python fake and not a full AIAgent/provider
integration. After inspecting `ready.json` and validating the exact tool/path/ID,
the worker called it once on the roundtrip fixture. Its actual response was one
line, 52 bytes. The worker removed only the tool's line-number presentation,
returned the 51-character synthetic line plus LF, and published a matched result
envelope. `native-audit.json` retains the actual tool arguments/response and
handoff lineage. The tool API did not expose a portable native audit-call ID;
none is invented. The original invocation/response is in this worker conversation.
The receipt is explicitly a worker record of that real call, not a fabricated
Hermes audit subsystem. No native tool was invoked for the cancellation fixture.

A random private fixture nonce and its SHA256 were frozen **before** launch. The
prompt contained only the fixture path and task, not its value or an answer key.
Exact native-to-MCP text SHA256:
`33018ecb650591d2c4862334939f449785f859f7e5a2513ee923c8b0f74aaf09`.
The model's final single-line answer matched that oracle after normalizing the
trailing newline; this is not a claim about byte-exact model text framing.

## Verified runtime controls and frozen commands

Installed help and the supplied official CLI reference establish print/stream
output, partial messages, `--restricted`, empty built-ins, strict MCP config,
scoped permissions, skills disabling and nonpersistent sessions. `--max-turns`
is documented even though absent from normal installed help. Non-inference
`--version` invocations accepted the exact prepared options, including the turn
limit, and returned `2.1.283 (Claude Code)` with exit0. No `--bare` (which excludes
subscription auth), `--safe-mode` (which disables MCP), bypassPermissions,
fallback model, resume, background agent, or cloud-session option was used.

Per-process controls actually used:

- `--tools ''`, `--strict-mcp-config` with only the owned stdio server;
  `--allowedTools mcp__harness_probe__fixture_read`, `--permission-mode dontAsk`,
  and `--permission-prompts none`. Actual init advertised **only that MCP tool**
  in both cases, not Bash/Read/other built-ins (nor EndConversation).
- `--restricted --setting-sources ''`, explicit settings `disableAllHooks=true`,
  `autoMemoryEnabled=false`, `syncClaudeAiPlugins=false`, `claudeMdExcludes=['**']`;
  `--disable-slash-commands`, `--no-chrome`, and a small replacement system prompt.
  An empty owned `CLAUDE_CODE_PLUGIN_CACHE_DIR` prevents installed plugin
  discovery from using the ordinary plugin root. Settings and cache changes are
  confined to ignored task-private files, not the user's live configuration.
- An explicit minimal OS environment retains subscription HOME for official
  runtime-owned auth, but inherits no API keys/provider overrides/other agent
  variables. Documented env controls disable nonessential traffic, marketplace
  autoinstall, CLAUDE.md, auto-memory, background tasks, cron, compaction,
  claude.ai connectors and deferred tool search. Managed runtime policy still
  applies; no claim of bypassing or globally disabling it.
- `CLAUDE_CODE_MAX_RETRIES=0` and
  `CLAUDE_CODE_DISABLE_NONSTREAMING_FALLBACK=1`; no client relaunch/retry.
  `--effort low`; requested output cap `CLAUDE_CODE_MAX_OUTPUT_TOKENS=1024`.
  The request envelope was not intercepted: the effective wire cap/internal
  request count is not independently proven. `modelUsage.maxOutputTokens=128000`
  is reported model metadata, not proof the requested cap was ignored or applied.

Before first inference, minimal-env official `claude auth status` returned exit0,
`loggedIn=true`, `authMethod=claude.ai`, `subscriptionType=max`,
`apiProvider=firstParty`. Only those fields and exit were retained; account/email/
config/token fields and raw output were discarded in memory. Historical logged-out
controller input is unchanged and explicitly superseded by this observation.
Only the official binary accessed its own stored subscription auth. No login,
credential extraction/copy, API/Console route, account setting change or update.

The exact CLI argv/environment/settings/schema/oracle for **both** cases were
frozen in ignored `private/capability/freeze.json` and each `case.json` before the
first launch. The preparation source/command is retained as
`private/capability/prepare.py`, executed once with:

```sh
python3 private/capability/prepare.py
```

Actual live observer commands (each executed exactly once):

```sh
python3 spikes/claude-runtime-capability/probe.py run private/capability roundtrip
python3 spikes/claude-runtime-capability/probe.py run private/capability cancel
```

Each case uses an exclusive launch marker, fresh owned directory and process
group, no session persistence, a 60s normal response boundary and 120s hard
ceiling with 5s TERM grace then group kill/reap. The parent handles interruption;
cleanup is idempotent. Runtime retries were disabled by the supported controls
above, but process/turn counts are not exact wire-request accounting. The
roundtrip limit was two agentic turns; cancellation limit one. Maximum two model
session launches / four combined child minutes. **Both live slots are consumed;
reviewers must not rerun them.** An error creates STOP, and failed cases are not
resubmitted. A reused successful case directory also cannot relaunch.

## Actual observations, not mocks

| Case | Real model tool-use ID | MCP RPC ID | Observed result |
| --- | --- | --- | --- |
| Roundtrip | `toolu_01PZ1BPfhYEXHzRtXmFWBJkz` | `2` | PASS; one native read, one matched MCP return, final fixture oracle; CLI exit0, reported2 turns, 18.9042s |
| Pending cancellation | `toolu_01LzxiAZxyVoSTKKh7a9qWZk` | `2` | PASS; zero native reads/results/deliveries/MCP returns; intentional CLI termination exit143, 4.8615s |

RPC IDs are local to distinct case servers, **not model tool-use IDs**. In the
roundtrip, observed monotonic order was: real ID stream start 2706898.5965;
complete assistant arguments 2706899.3447; stream block stop 2706899.3504;
MCP parked 2706899.3511; validated ready 2706899.3523; native result delivery
2706913.6640; same RPC/model-lineage MCP return 2706913.6827; continuation
message 2706915.0625; success 2706915.1109. These are actual retained events,
not synthetic IDs or a permission callback used as a replacement result.

Both init selections and each observed message start/assistant identified
`claude-opus-5-5`. Roundtrip result `modelUsage` also identifies canonical model
`claude-opus-5-5` and provider `firstParty`; `apiKeySource=none` in both init
records is consistent with the separately observed subscription route, not a
standalone auth proof. Roundtrip reported input4/cache-create1435/cache-read1257/
output150 tokens and estimated list cost USD0.0147474. Per-assistant usage output
was 32 then38, not an independently reconciled total. Cancellation observed one
assistant/tool request with input2/cache-create1251/output32 and **no final usage
result**. There were two assistant messages in the roundtrip and one in cancel;
no exact provider-wire or internal auxiliary-request count is claimed.

Both owned leaders were reaped and both groups absent after cleanup, including
repeated cleanup. Combined child lifetime **23.7657s**. CLI stderr was empty in
both. The terminal background launcher itself printed zsh/gitstatus initialization
warnings; these were outside the minimal-env official child and are not Claude
execution/tool evidence. No duplicate native tool, stale response, session resume
or orphan owned group was observed. This is serial mediation only: identical
parallel calls, broad cancellation races and cross-role lifecycles remain unproven.

## Local tests and publication checks

[test_probe.py](test_probe.py) contains **10 offline cases**: event-shaped serial
correlation; mismatched results; duplicate/stale cancellation; unexpected calls;
MCP mailbox-only behavior; MCP cancellation; real sleeping-child deadline/reaping;
real descendant process-group cleanup; exclusive mailbox; value-blind projection.
The nonexistent fixture plus file-open scope/child-execution denial checks that
MCP itself cannot satisfy the read. These cases do not start Claude, contact
services, or read profiles/credentials. They prove local code mechanisms, **not
live Claude behavior**. Owned tests use only task-private directories and Python
children. An initial 10-case run failed on a test guard rejecting an owned file
descriptor and transient macOS group-state EPERM; both original errors are retained.
EPERM is not treated as absence: the code checks the exact owned PGID using ps.
The corrected 10-case run passed; no live case was retried for these offline fixes.

Frozen checks (run from the assigned worktree):

```sh
python3 -m unittest discover -s spikes/claude-runtime-capability -p 'test_*.py' -v
python3 private/capability/verify.py
git diff --check 4cf9c892383647efda613b91c6054eba94260faf
gitleaks dir --redact --no-banner spikes/claude-runtime-capability
git diff --cached --stat
git diff --cached -- spikes/claude-runtime-capability
```

The one-off `verify.py` source is retained privately before execution: AST syntax,
exact three-file owned scope/baseline/ref/branch, Markdown fences/embedded shell
syntax/new relative links, frozen source hash, evidence lineage/order, two launch
counts, native result hash and both cleanup oracles. Full outputs/staged diff and
semantic/publication review are retained under `private/capability/` and bound to
the candidate SHA/tree for same-card **harness-reviewer** review. No broad/live-
sensitive suite or verify-state is appropriate or was run for this isolated spike.

## Source provenance, retained evidence and next decision

Five supplied immutable controller/public snapshots were hash-verified against
`private/controller-inputs/manifest.json`; observations.json was read before any
execution. Their CLI/headless/model docs and official Hermes provider reference
were reused without refetching. The documented Opus5.5 ID/minimum2.1.280 was
subsequently corroborated by actual runtime metadata above, not model self-report.
No old source campaign or its tests was rerun.

Six permitted new anonymous GET attempts, 30s/no retries/pagination: the `.md`
forms of env-vars, settings-reference and memory each returned403 (common body
SHA256 `2938e9f1284180959e33ab1718d0793a72ff6e4cdb8108c34dcd14e69446de5c`).
Their distinct HTML interfaces then returned200:

| Official URL | Retrieved UTC | SHA256 |
| --- | --- | --- |
| https://code.claude.com/docs/en/env-vars | 2026-10-17T00:20:47.940138+00:00 | `db0227cbf4e9395a4d2386042d1102ace1e3bea2a5941633c1a5b518ac8a303a` |
| https://code.claude.com/docs/en/settings-reference | 2026-10-17T00:20:48.747659+00:00 | `d9d3f375d2999cd6af52aaaae299767b120c9f1b31105bb0d2700d46833d039d` |
| https://code.claude.com/docs/en/memory | 2026-10-17T00:20:49.185490+00:00 | `f91d82cc158f0d962c369a6df1438ccfe2ec0e3ae27afe262df95a071973bb5c` |

Exact URLs/statuses/hashes/times and responses are in `get-receipts.json` and the
owned snapshots. These are retrieval snapshots, not a pinned source release or
universal version support. No downloaded source was executed or package installed.
Private evidence includes sanitized auth/init/model/usage events (no raw thinking,
account identities, credentials or full runtime transcripts), frozen commands,
launch markers, pending/ready/delivery/MCP-return/outcome receipts, the synthetic
native audit and verification outputs. Private files are owner-only where suitable;
no secret values are stored there or published.

The supplied Max20x/credits-OFF/$0 facts and owner-reported absence of alternative
billing routes justified these included-allowance observations. Independent
auto-reload state remains unverified. No new account-side before/after usage was
measured: runtime list-price estimates are **not** a charge or proof of included
pool consumption. No extra usage was enabled/purchased and no fallback selected.
Private/local unmodified-runtime observation is not a provider terms exemption or
claim of Anthropic endorsement.

Next decision: independent review may accept this **serial capability artifact**
and recommend a separately scoped small provider implementation. Do not expand
this card into it or consume another live session. Full Hermes client/tool-round
translation, parallel identity, role/helper selection, OpenAI/Zai portability,
quota/construction errors, billing attribution, supported version range, measured
role workflow and rollout remain **UNRUN**. Existing native NATIVE_FAILURE/M1
UNRUN and historical offline diagnostic stops remain unchanged. No push, PR,
production/cloud action, live policy/profile/plugin deployment or cutover.
