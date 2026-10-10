# Prompt-injection scanning: `POST /api/v1/scan/injection`

Dedicated endpoint for scanning untrusted text (fetched pages, uploads, emails,
retrieved documents, repository files) before an agent reads it. It needs only
the `scan:injection` API-key scope. `/filter` remains the combined
PII + toxicity + injection endpoint and still requires `filter:*` scopes.

## Request

```json
{
  "content": "…",
  "profile": "third_party_document | user_brief | code_docs",
  "return_content": false,
  "store": false,
  "fast_mode": false,
  "source_id": "optional caller correlation id"
}
```

| field | default | notes |
|---|---|---|
| `profile` | `third_party_document` (server setting `PROMPT_INJECTION_DEFAULT_PROFILE`) | Pick by **where the text came from**, not what it is about. Fetched/uploaded = `third_party_document`. The user's own brief/spec = `user_brief`. READMEs, API docs, AGENTS.md, code = `code_docs`. |
| `return_content` | `false` | Echo `content` back. Off by default so proxies and logs never see it. |
| `store` | `false` | Keep the result in memory so `GET /scan/injection/results/{id}` works. Off by default. |
| `fast_mode` | `false` | Regex rules only, no classifier. Not marked degraded (you asked for it). |

Maximum content length is `MAX_FILTER_CONTENT_CHARS` (100,000). Larger bodies return 413.

## Response

```json
{
  "id": "…",
  "verdict": "allow | monitor | flag | block | unavailable",
  "score": 0.0,
  "degraded": false,
  "degraded_reason": null,
  "reasons": [{"code": "instruction_override", "strong": true, "tier": "strong",
               "severity": 0.9, "channel": "body", "quoted": false, "position": [120, 152]}],
  "chunks": {"total": 12, "scanned": 12, "failed": 0, "flagged": 1,
             "spans": [{"source": "body", "start": 0, "end": 1790, "score": 0.97}]},
  "signals": {"normalization": [{"code": "zero_width_chars", "count": 5}],
              "decoded_payloads": [{"encoding": "base64", "start": 40, "end": 120, "chars": 61}],
              "hidden_channels": [{"kind": "html_comment", "start": 300, "end": 420}]},
  "arbiter": null,
  "model_version": "protectai/deberta-v3-base-prompt-injection-v2@e6535ca4ce3b",
  "policy_version": "2026.10-rules-v1",
  "profile": "third_party_document",
  "content_sha256": "…",
  "content_length": 18234,
  "detector": "hybrid",
  "latency_ms": 212.4,
  "analyzed_at": "…",
  "content": null
}
```

### How to act on a verdict

| verdict | HTTP | meaning | suggested handling |
|---|---|---|---|
| `allow` | 200 | nothing of note | proceed |
| `monitor` | 200 | weak signal (role-change phrasing, odd delimiters, a quoted attack string, mild classifier score) | proceed; log |
| `flag` | 200 | classifier confident **or** a strong rule hit **or** a supply-chain convention | proceed only with the text treated as data; show the user what was found |
| `block` | 200 | classifier ≥ block threshold **and** an unquoted strong rule | do not pass to the agent |
| `unavailable` | **503** | part of the scan did not run (`degraded_reason` says why) | **do not treat as safe**; retry or fall back to `block`-like handling |

`degraded: true` can also accompany `flag`/`block` (e.g. a strong rule fired but
some chunks failed). It never accompanies `allow`.

### Reasons

`tier` is one of:

- `strong` — sufficient alone for `flag`: `instruction_override`, `new_instruction`,
  `system_prompt_extraction`, `exfiltration_command`, `dan_mode`, `unrestricted_mode`,
  `ai_addressed`, `tool_hijack`.
- `weak` — never escalates past `monitor` on its own: `role_change`, `system_impersonation`,
  `delimiter_injection`, `context_switching`, `future_instruction`, `unicode_escape`,
  `context_marker_manipulation`, `encoded_payload`, `zero_width_chars`, `unicode_tag_chars`,
  `homoglyph_chars`, `private_use_chars`.
- `supply_chain` — capped at `flag`: `pipe_to_shell`, `disable_review_or_ci`,
  `untrusted_dependency_source`, `new_network_host`. These fire on the *mandate* shape
  ("must always run `curl … | sh`", "do not review the script", "agents must merge directly
  to main"), not on the install one-liner every README contains.

`quoted: true` means the match is *mentioned*, not *used*: it sits inside inline quotes or
is introduced by descriptive framing ("attempts to reveal the system prompt", "phrases like
…"). Quoted strong matches count as weak. Matches inside hidden channels or decoded payloads
are never marked quoted.

`channel` is `body`, `channel:<kind>` (`html_comment`, `html_alt_or_title`,
`html_hidden_element`, `markdown_link_title`, `markdown_image_alt`, `code_line_comment`,
`code_block_comment`, `python_docstring`, `package_json_script`, …) or
`decoded:<encoding>` (`base64`, `base64url`, `hex`, `escape_sequence`, `rot13`).

### Chunks

The classifier accepts 512 tokens. Text is split by **tokens** (448 + 64 overlap), so dense
inputs (code, base64, CJK) are fully covered. `spans` carries every chunk's score and
character offsets; `flagged` counts chunks at or above the profile's flag threshold, so a
caller can tell "1 of 12 chunks" from "pervasive". Decoded payloads and hidden-channel text
are scored as extra chunks (`source` ≠ `body`).

## Profiles and thresholds

`GET /api/v1/scan/injection/profiles` returns the live values. Starting values:

| profile | block (classifier ∧ strong rule) | flag (classifier alone) | monitor | weak rule alone |
|---|---|---|---|---|
| `third_party_document` | ≥ 0.90 | ≥ 0.75 | ≥ 0.30 | monitor |
| `code_docs` | ≥ 0.95 | ≥ 0.85 | ≥ 0.40 | monitor |
| `user_brief` | ≥ 0.97 | ≥ 0.90 | ≥ 0.50 | allow |

The classifier saturates near 1.0 on anything security-flavoured, so profiles mostly change
how much weight an unsupported classifier score carries. Rules decide BLOCK.

## Optional LLM arbiter

Off by default (`PROMPT_INJECTION_ARBITER_ENABLED=false`). When on, a BLOCK verdict is
sent — as quoted data inside `<document>` tags — to a classifier prompt that answers in JSON
whether the text is *addressed to* an AI or *about* AI. It may only move BLOCK down to FLAG.
Any error, timeout or unparsable answer is a no-op. Provider/model:
`PROMPT_INJECTION_ARBITER_PROVIDER` (`openai` | `anthropic`), `PROMPT_INJECTION_ARBITER_MODEL`.

## Batch

`POST /api/v1/scan/injection/batch` with `{"documents": [ScanRequest, …], "profile": "…"}`,
at most `SCAN_INJECTION_BATCH_MAX` (8) documents. Returns per-document results in order,
plus `worst_verdict`. Counts as one request for rate limiting. Returns 503 only if every
document is `unavailable`.

## Feedback

`POST /api/v1/scan/injection/feedback`

```json
{"content_sha256": "…", "label": "false_positive | false_negative | true_positive | true_negative",
 "verdict_seen": "flag", "profile": "code_docs", "category": "benign_technical",
 "model_version": "…", "policy_version": "…", "notes": "…"}
```

Only the hash is stored (table `injection_feedback`). Keep the content on your side and join
on the hash when assembling an eval set.

## Retention and privacy

- Content is **never** logged. Logs carry the first 16 hex chars of `content_sha256`, the
  verdict, score, degraded flag and chunk counts.
- Content is **not** echoed unless `return_content: true`.
- Nothing is retained unless `store: true`; stored results live in a bounded in-process map
  (10,000 entries, FIFO eviction, lost on restart) and are only readable by the owning user.
- `/filter` keeps its historical defaults (`return_content: true`, `store: true`) for
  backward compatibility; pass `false` for both to get the same guarantees there.
- Feedback rows contain hashes and labels only.

## Rate limits

Two limiters apply, both returning **429 with `Retry-After`** (seconds):

- per API key: the key's own `rate_limit_per_minute` / `rate_limit_per_hour`
  (defaults 60 / 1,000; set at key creation);
- per client IP (global middleware): `RATE_LIMIT_PER_MINUTE` / `RATE_LIMIT_PER_HOUR`
  (defaults 1,000 / 10,000). `X-RateLimit-*` headers report remaining budget.

## Evaluation and CI gates

```
cd backend
./venv/bin/python eval/fetch_corpus.py              # one-time: public docs → eval/corpus/
./venv/bin/python eval/run_eval.py                  # full run (needs the model); writes eval/results/
./venv/bin/python eval/run_eval.py --gates          # exit 1 on any gate in eval/gates.json
./venv/bin/python eval/run_eval.py --regex-only     # fast smoke
./venv/bin/python eval/run_eval.py --model deepset/deberta-v3-base-injection --tag alt
./venv/bin/python eval/run_eval.py --save-baseline  # promote to eval/baseline.json
RAMPART_MODEL_TESTS=1 ./venv/bin/python -m pytest tests/test_injection_regression.py
```

`fetch_corpus.py` pulls the benign side of the corpus from ~35 public GitHub repositories
at eval time; it is never committed (`backend/eval/corpus/` is gitignored). See
[`docs/EVAL_CORPUS_SOURCES.md`](EVAL_CORPUS_SOURCES.md) for the full source list and license
of each.

Corpus categories: `benign_technical` (READMEs, API docs, specs, changelogs, runbooks,
AGENTS.md-style files), `benign_about_ai` (OWASP LLM Top 10, guardrail/detector docs,
red-team write-ups), `benign_imperative` (git/docker/gh man pages, tutorials). Attack families
are generated in `eval/attacks.py`: direct, indirect through every hidden channel, multilingual,
encoded (base64/hex/rot13/escapes/tag chars/zero-width), homoglyph, chunk-straddle, buried in
long documents, tool-hijack, and convention-shaped. Convention-shaped and multilingual are
tracked in `eval/known_gaps.json` and do not gate.

Reported: BLOCK and FLAG+ false-positive rate per category and per length bucket
(1k/5k/20k/100k), recall per family at FLAG+ and BLOCK, AUROC, a calibration curve and
p50/p95 latency by length. Gates fail on absolute thresholds and on regression versus
`eval/baseline.json`.

### Baseline (2026-10-09, protectai/deberta-v3-base-prompt-injection-v2@e6535ca, policy 2026.10-rules-v1)

Natural profiles, 1,359 benign / 249 attacks, all gates passing:

| | BLOCK FPR | FLAG+ FPR |
|---|---|---|
| benign_technical (707, `code_docs`) | 0.3% | 7.5% |
| benign_imperative (221, `code_docs`) | 0.0% | 4.5% |
| benign_about_ai (431, `user_brief`) | 2.1% | 26.5% |

Recall at FLAG+: direct 100%, every indirect channel 92–100%, encoded 100%, homoglyph 100%,
buried-in-long 100%, chunk-straddle 100%, tool-hijack 100%, multilingual 75% (known gap),
convention-shaped 87.5% (known gap). All gating families 97.5%. AUROC 0.93 (classifier alone 0.88).
Latency on CPU (PyTorch, 8 chunk threads): p95 0.2 s at ≤1k chars, 0.45 s at ≤5k, 1.2 s at ≤20k,
4 s at ≤100k.

The 26.5% FLAG+ rate on about-AI docs is the classifier saturating on security prose (OWASP,
red-team docs score ≥ 0.9 regardless of profile); it is why BLOCK requires a rule and why the
arbiter exists. Reducing it further needs the arbiter or a different classifier.

### Model comparison

`deepset/deberta-v3-base-injection` was run on the same attacks and 180 benign documents. It
scores **every** multi-paragraph document ≥ 0.98 (`## Install … run pytest` × 20 → 0.98) — it was
trained on short prompts — giving FLAG+ FPR of 100% on all benign categories. Recall at BLOCK
was higher only because of that saturation. Not viable; ProtectAI v2 stays. Candidates worth
trying next: Meta Prompt-Guard-86M (gated download) and a long-context classifier fine-tuned on
documents rather than prompts.
