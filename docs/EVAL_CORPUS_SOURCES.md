# Eval Corpus Sources & Licenses

The prompt-injection evaluation (`backend/eval/`) measures false-positive rate on a corpus
of **benign** documents — ordinary API docs, READMEs, changelogs, security writeups, CLI
tutorials — so we know the detector doesn't flag normal developer content. That corpus is
not written by us; it's fetched on demand from public GitHub repositories by
[`backend/eval/fetch_corpus.py`](../backend/eval/fetch_corpus.py) (`make eval-corpus`).

**None of this is redistributed in this repository.** `backend/eval/corpus/` is gitignored;
fetching populates a local, disposable cache used only to run the eval, and CI fetches its
own copy on every run. This page exists so it's clear what's being pulled in and under what
terms, for anyone auditing the project or adding a new source.

Every `Source` entry in `fetch_corpus.py` carries a `license` field, which should reflect
that repository's actual `LICENSE` file — not an assumption. The table below is generated
from that list; regenerate it with:

```bash
cd backend && ./venv/bin/python eval/fetch_corpus.py --print-sources
```

and paste the output in below whenever `SOURCES` changes. Last generated: 2026-10-09.

<!-- BEGIN GENERATED: python eval/fetch_corpus.py --print-sources -->
| Category | Repository | License | Content |
|---|---|---|---|
| benign_technical | [fastapi/fastapi](https://github.com/fastapi/fastapi) | MIT | api_docs |
| benign_technical | [pydantic/pydantic](https://github.com/pydantic/pydantic) | MIT | api_docs |
| benign_technical | [encode/httpx](https://github.com/encode/httpx) | BSD-3 | api_docs |
| benign_technical | [pallets/flask](https://github.com/pallets/flask) | BSD-3 | api_docs |
| benign_technical | [psf/requests](https://github.com/psf/requests) | Apache-2.0 | api_docs |
| benign_technical | [kubernetes/website](https://github.com/kubernetes/website) | CC-BY-4.0 | spec |
| benign_technical | [kubernetes/website](https://github.com/kubernetes/website) | CC-BY-4.0 | runbook |
| benign_technical | [prometheus/docs](https://github.com/prometheus/docs) | Apache-2.0 | runbook |
| benign_technical | [grafana/grafana](https://github.com/grafana/grafana) | AGPL-3.0 | runbook |
| benign_technical | [tiangolo/typer](https://github.com/tiangolo/typer) | MIT | api_docs |
| benign_technical | [encode/starlette](https://github.com/encode/starlette) | BSD-3 | changelog |
| benign_technical | [pydantic/pydantic](https://github.com/pydantic/pydantic) | MIT | changelog |
| benign_technical | [encode/httpx](https://github.com/encode/httpx) | BSD-3 | changelog |
| benign_technical | [python/cpython](https://github.com/python/cpython) | PSF | changelog |
| benign_technical | [openai/codex](https://github.com/openai/codex) | Apache-2.0 | agents_md |
| benign_technical | [PatrickJS/awesome-cursorrules](https://github.com/PatrickJS/awesome-cursorrules) | CC0 | agents_md |
| benign_technical | [modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers) | MIT | readme |
| benign_technical | [sindresorhus/awesome](https://github.com/sindresorhus/awesome) | CC0 | readme |
| benign_about_ai | [OWASP/www-project-top-10-for-large-language-model-applications](https://github.com/OWASP/www-project-top-10-for-large-language-model-applications) | CC-BY-SA-4.0 | owasp |
| benign_about_ai | [OWASP/CheatSheetSeries](https://github.com/OWASP/CheatSheetSeries) | CC-BY-SA-4.0 | security_cheatsheet |
| benign_about_ai | [NVIDIA/NeMo-Guardrails](https://github.com/NVIDIA/NeMo-Guardrails) | Apache-2.0 | guardrails_docs |
| benign_about_ai | [protectai/llm-guard](https://github.com/protectai/llm-guard) | MIT | detector_docs |
| benign_about_ai | [promptfoo/promptfoo](https://github.com/promptfoo/promptfoo) | MIT | redteam_docs |
| benign_about_ai | [NVIDIA/garak](https://github.com/NVIDIA/garak) | Apache-2.0 | redteam_docs |
| benign_about_ai | [anthropics/anthropic-cookbook](https://github.com/anthropics/anthropic-cookbook) | MIT | ai_docs |
| benign_about_ai | [openai/openai-cookbook](https://github.com/openai/openai-cookbook) | MIT | ai_docs |
| benign_about_ai | [greshake/llm-security](https://github.com/greshake/llm-security) | MIT | paper_summary |
| benign_about_ai | [microsoft/promptbench](https://github.com/microsoft/promptbench) | MIT | paper_summary |
| benign_imperative | [git/git](https://github.com/git/git) | GPL-2.0 | cli_man |
| benign_imperative | [docker/docs](https://github.com/docker/docs) | Apache-2.0 | tutorial |
| benign_imperative | [docker/docs](https://github.com/docker/docs) | Apache-2.0 | cli_docs |
| benign_imperative | [cli/cli](https://github.com/cli/cli) | MIT | cli_docs |
| benign_imperative | [rust-lang/book](https://github.com/rust-lang/book) | MIT | tutorial |
| benign_imperative | [ohmyzsh/ohmyzsh](https://github.com/ohmyzsh/ohmyzsh) | MIT | cli_docs |
| benign_imperative | [Homebrew/brew](https://github.com/Homebrew/brew) | BSD-2 | cli_docs |
<!-- END GENERATED -->

## Notes

- **Copyleft sources** (`git/git` GPL-2.0, `grafana/grafana` AGPL-3.0) are docs/man-pages,
  fetched only into the local disposable eval cache — never redistributed, modified, or
  shipped — so none of their copyleft obligations (share-alike, source disclosure) are
  triggered. If that ever changes (e.g. someone proposes checking the corpus into git),
  these two need re-review first.
- **CC-BY / CC-BY-SA sources** (OWASP, Kubernetes) require attribution if redistributed;
  again moot while the corpus stays local-only, but keep in mind if that changes.
