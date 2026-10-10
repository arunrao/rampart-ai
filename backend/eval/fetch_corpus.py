"""
Fetch public benign documents into eval/corpus/<category>/.

Sources are public GitHub repositories (documentation trees). Each document is
saved as plain text with a small JSON sidecar recording its origin and license
hint. Re-running is idempotent (existing files are skipped). The ``corpus/``
output directory is gitignored: nothing fetched here is redistributed in this
repository, but ``license`` on each ``Source`` should still reflect the
upstream repo's actual LICENSE file, not an assumption — verified against each
repository's LICENSE as of 2026-10-09; re-check before adding a new source.

    python eval/fetch_corpus.py              # fetch everything
    python eval/fetch_corpus.py --category benign_about_ai --limit 50

Set GITHUB_TOKEN to raise the GitHub API rate limit (60/h unauthenticated;
one tree call per source is needed).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

import httpx

CORPUS_DIR = Path(__file__).parent / "corpus"
TEXT_EXT = re.compile(r"\.(md|mdx|rst|txt|adoc|asciidoc)$", re.I)


@dataclass
class Source:
    category: str
    repo: str            # owner/name
    ref: str             # branch
    path_prefix: str     # directory inside the repo ("" = whole repo)
    include: str = r".*"  # regex on the path (after prefix)
    max_files: int = 400
    license: str = "see repository"
    kind: str = "docs"


SOURCES: List[Source] = [
    # ---- benign technical: READMEs, API docs, specs, changelogs, runbooks ------
    Source("benign_technical", "fastapi/fastapi", "master", "docs/en/docs/", r"\.md$", 220, "MIT", "api_docs"),
    Source("benign_technical", "pydantic/pydantic", "main", "docs/", r"\.md$", 120, "MIT", "api_docs"),
    Source("benign_technical", "encode/httpx", "master", "docs/", r"\.md$", 40, "BSD-3", "api_docs"),
    Source("benign_technical", "pallets/flask", "main", "docs/", r"\.rst$", 80, "BSD-3", "api_docs"),
    Source("benign_technical", "psf/requests", "main", "docs/", r"\.rst$", 40, "Apache-2.0", "api_docs"),
    Source("benign_technical", "kubernetes/website", "main", "content/en/docs/concepts/", r"\.md$", 200, "CC-BY-4.0", "spec"),
    Source("benign_technical", "kubernetes/website", "main", "content/en/docs/tasks/run-application/", r"\.md$", 40, "CC-BY-4.0", "runbook"),
    Source("benign_technical", "prometheus/docs", "main", "docs/", r"\.md$", 80, "Apache-2.0", "runbook"),
    Source("benign_technical", "grafana/grafana", "main", "docs/sources/alerting/", r"\.md$", 60, "AGPL-3.0", "runbook"),
    Source("benign_technical", "tiangolo/typer", "master", "docs/", r"release-notes\.md$|\.md$", 60, "MIT", "api_docs"),
    # changelogs
    Source("benign_technical", "encode/starlette", "master", "docs/", r"release-notes\.md$", 2, "BSD-3", "changelog"),
    Source("benign_technical", "pydantic/pydantic", "main", "", r"^HISTORY\.md$", 1, "MIT", "changelog"),
    Source("benign_technical", "encode/httpx", "master", "", r"^CHANGELOG\.md$", 1, "BSD-3", "changelog"),
    Source("benign_technical", "python/cpython", "main", "Misc/NEWS.d/", r"\.rst$", 30, "PSF", "changelog"),
    # agent instruction files (AGENTS.md / CLAUDE.md / .cursorrules style)
    Source("benign_technical", "openai/codex", "main", "", r"(^|/)AGENTS\.md$", 20, "Apache-2.0", "agents_md"),
    Source("benign_technical", "PatrickJS/awesome-cursorrules", "main", "rules/", r"\.cursorrules$|\.md$|\.mdc$", 120, "CC0", "agents_md"),
    # Repo license is transitioning to Apache-2.0; pre-transition content (what these
    # per-server READMEs still are) remains MIT per the repo's LICENSE file.
    Source("benign_technical", "modelcontextprotocol/servers", "main", "src/", r"README\.md$", 40, "MIT", "readme"),
    Source("benign_technical", "sindresorhus/awesome", "main", "", r"^readme\.md$", 1, "CC0", "readme"),
    # issue / PR threads are not fetched (API shaped); rely on changelogs + runbooks for that register

    # ---- benign about AI / security -------------------------------------------
    Source("benign_about_ai", "OWASP/www-project-top-10-for-large-language-model-applications", "main", "", r"\.md$", 120, "CC-BY-SA-4.0", "owasp"),
    Source("benign_about_ai", "OWASP/CheatSheetSeries", "master", "cheatsheets/", r"(LLM|AI|Prompt|Injection|Secrets|Authentication|Authorization|Input_Validation|XSS|Logging|Session|Password|OAuth|JSON|Transport|Vulnerable|Threat|Secure).*\.md$", 60, "CC-BY-SA-4.0", "security_cheatsheet"),
    Source("benign_about_ai", "NVIDIA/NeMo-Guardrails", "develop", "docs/", r"\.md$", 120, "Apache-2.0", "guardrails_docs"),
    Source("benign_about_ai", "protectai/llm-guard", "main", "docs/", r"\.md$", 60, "MIT", "detector_docs"),
    Source("benign_about_ai", "promptfoo/promptfoo", "main", "site/docs/red-team/", r"\.md$", 120, "MIT", "redteam_docs"),
    Source("benign_about_ai", "NVIDIA/garak", "main", "docs/source/", r"\.rst$|\.md$", 80, "Apache-2.0", "redteam_docs"),
    Source("benign_about_ai", "anthropics/anthropic-cookbook", "main", "", r"README\.md$", 40, "MIT", "ai_docs"),
    Source("benign_about_ai", "openai/openai-cookbook", "main", "articles/", r"\.md$", 40, "MIT", "ai_docs"),
    Source("benign_about_ai", "greshake/llm-security", "main", "", r"README\.md$", 1, "MIT", "paper_summary"),
    Source("benign_about_ai", "microsoft/promptbench", "main", "", r"README\.md$|docs/.*\.md$", 20, "MIT", "paper_summary"),
    # jthack/PIPE and meta-llama/PurpleLlama were removed: PIPE carries no LICENSE file
    # (all rights reserved by default), and PurpleLlama's READMEs (Llama Guard, Prompt
    # Guard, ...) fall under the Llama Community License, not the MIT label this list
    # previously gave them. Do not re-add either without an accurate license and, for
    # PurpleLlama, without checking which specific paths are actually MIT (evals/
    # benchmarks and CodeShield only — see https://github.com/meta-llama/PurpleLlama).

    # ---- benign imperative-heavy: tutorials and CLI docs -----------------------
    Source("benign_imperative", "git/git", "master", "Documentation/", r"^git-[a-z-]+\.(txt|adoc)$", 120, "GPL-2.0", "cli_man"),
    Source("benign_imperative", "docker/docs", "main", "content/get-started/", r"\.md$", 60, "Apache-2.0", "tutorial"),
    Source("benign_imperative", "docker/docs", "main", "content/reference/cli/docker/", r"\.md$", 60, "Apache-2.0", "cli_docs"),
    Source("benign_imperative", "cli/cli", "trunk", "docs/", r"\.md$", 20, "MIT", "cli_docs"),
    Source("benign_imperative", "rust-lang/book", "main", "src/", r"ch0[1-5].*\.md$", 40, "MIT", "tutorial"),
    Source("benign_imperative", "ohmyzsh/ohmyzsh", "master", "plugins/", r"README\.md$", 60, "MIT", "cli_docs"),
    Source("benign_imperative", "Homebrew/brew", "master", "docs/", r"\.md$", 40, "BSD-2", "cli_docs"),
]


def _client() -> httpx.Client:
    headers = {"User-Agent": "rampart-eval-corpus/1.0", "Accept": "application/vnd.github+json"}
    tok = os.getenv("GITHUB_TOKEN")
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    return httpx.Client(headers=headers, timeout=30.0, follow_redirects=True)


def _tree(client: httpx.Client, src: Source) -> List[str]:
    url = f"https://api.github.com/repos/{src.repo}/git/trees/{src.ref}?recursive=1"
    for attempt in range(3):
        r = client.get(url)
        if r.status_code == 200:
            break
        if r.status_code in (403, 429):
            reset = int(r.headers.get("x-ratelimit-reset", time.time() + 60))
            wait = max(5, min(120, reset - int(time.time())))
            print(f"  rate limited on {src.repo}; sleeping {wait}s", file=sys.stderr)
            time.sleep(wait)
            continue
        print(f"  tree fetch failed for {src.repo}@{src.ref}: {r.status_code}", file=sys.stderr)
        return []
    else:
        return []
    inc = re.compile(src.include)
    paths = []
    for node in r.json().get("tree", []):
        p = node.get("path", "")
        if node.get("type") != "blob" or not p.startswith(src.path_prefix):
            continue
        rel = p[len(src.path_prefix):]
        if TEXT_EXT.search(p) and inc.search(rel):
            paths.append(p)
    return sorted(paths)[: src.max_files]


def _safe_name(repo: str, path: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", f"{repo}__{path}")[:180]


def fetch(categories: Optional[Iterable[str]] = None, limit: Optional[int] = None, min_chars: int = 400) -> int:
    saved = 0
    with _client() as client:
        for src in SOURCES:
            if categories and src.category not in categories:
                continue
            out_dir = CORPUS_DIR / src.category
            out_dir.mkdir(parents=True, exist_ok=True)
            paths = _tree(client, src)
            print(f"{src.category:18s} {src.repo:60s} {len(paths):4d} candidates")
            n = 0
            for p in paths:
                if limit and n >= limit:
                    break
                dest = out_dir / (_safe_name(src.repo, p) + ".txt")
                if dest.exists():
                    n += 1
                    continue
                raw = f"https://raw.githubusercontent.com/{src.repo}/{src.ref}/{p}"
                try:
                    r = client.get(raw)
                except httpx.HTTPError as exc:
                    print(f"  skip {p}: {type(exc).__name__}", file=sys.stderr)
                    continue
                if r.status_code != 200 or len(r.text) < min_chars:
                    continue
                dest.write_text(r.text, encoding="utf-8")
                dest.with_suffix(".json").write_text(json.dumps({
                    "category": src.category, "kind": src.kind, "repo": src.repo, "ref": src.ref,
                    "path": p, "url": raw, "license": src.license, "chars": len(r.text),
                }, indent=1))
                saved += 1
                n += 1
    return saved


def sources_markdown_table() -> str:
    """Render SOURCES as the attribution table in docs/EVAL_CORPUS_SOURCES.md."""
    lines = ["| Category | Repository | License | Content |", "|---|---|---|---|"]
    for src in SOURCES:
        lines.append(f"| {src.category} | [{src.repo}](https://github.com/{src.repo}) | {src.license} | {src.kind} |")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--category", action="append", help="restrict to category (repeatable)")
    ap.add_argument("--limit", type=int, help="max files per source")
    ap.add_argument(
        "--print-sources", action="store_true",
        help="print the SOURCES attribution table (markdown) and exit; used to regenerate "
             "docs/EVAL_CORPUS_SOURCES.md after editing SOURCES",
    )
    args = ap.parse_args()
    if args.print_sources:
        print(sources_markdown_table())
        return
    n = fetch(args.category, args.limit)
    counts = {d.name: len(list(d.glob("*.txt"))) for d in CORPUS_DIR.iterdir() if d.is_dir()}
    print(f"saved {n} new documents; corpus now: {counts}")


if __name__ == "__main__":
    main()
