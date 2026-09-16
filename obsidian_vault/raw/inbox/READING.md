---
type: raw
---
# Reading inbox

**Current aim: find a second strategy family for the autoresearch loop.** Drop anything that might
propose one: a trading strategy video, a paper, a blog post, a GitHub repo. Every source is screened
against what the harness can actually run, and the shortlist lives on the vault page
`wiki/concepts/strategy_family_search.md`.

**How to drop:** one item per line under Links, a URL first, then an optional ` — ` and a note.
YouTube, articles, arXiv papers, GitHub repos and PDFs are all fetched. A page that needs a login or
JavaScript can be clipped instead: save it as its own `.md` file in this folder with a `source:` URL
property (Obsidian Web Clipper does this) and it is read without any fetch. Non-link thoughts go
under Notes. Leave items here after they are processed or delete them; re-runs never duplicate.

**Then:** ask Claude Code to "fetch and review the reading inbox". It runs
`python -m knowledge.fetch_reading` (downloads each new link once) and records a summary and a
verdict for each source. Lines containing "example" and "delete me" are ignored.

## Links
- (example — delete me) https://www.youtube.com/watch?v=xxxx — the lecture I want summarized
- (example — delete me) https://arxiv.org/abs/xxxx — skim for the method, not the results
-

## Notes / raw text
(paste anything that is not a link here — a question, a topic to chase, a quote)
