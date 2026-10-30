# Brazilian legal retrieval: preliminary third-party due diligence

**Date:** 2026-10-30. **Decision:** research and pilot only; no dependency installed, copied or activated by this PR.

## Repository provenance and screening

| Candidate | Canonical source | Repository metadata inspected | Disposition |
|---|---|---|---|
| LexMCP / `mcp-juridico-brasil` | https://github.com/ehrodan/lexmcp | GitHub metadata: MIT; last pushed 2026-07-24; published tests and workflows exist. Repository history is shallow (one commit in the inspected snapshot). README claims LexML, DataJud and local corpus support. | **PILOT, isolated and read-only**. Audit all network/credential paths, transitive licenses, output accuracy, rate-limit behavior, and actual source coverage before use. README claims are not verified performance. |
| `EternoHelder/datasets-jur` | https://github.com/EternoHelder/datasets-jur | GitHub metadata: Apache-2.0 for repository; last pushed 2026-04-05. Sparse repository history. README describes STJ, DataJud and academic extraction scripts and explicitly says source data have separate terms. | **REJECT direct execution / integration**. The inspected STJ downloader interpolates untrusted remote API response data into a shell heredoc containing generated Python source and builds download URLs/file paths from remote metadata. These are injection/path-traversal risks requiring a safe-parser rewrite. Dataset rights remain separately unverified. |
| Awesome Legal Data | https://github.com/openlegaldata/awesome-legal-data | Curated directory with Brazilian links; last pushed 2026-10-20. No license classification established in inspected metadata. | **APPROVE as discovery reference only**; **INSUFFICIENT EVIDENCE** for bundling, re-licensing or integrating code/data. |
| ContractNLI | https://github.com/stanfordnlp/contract-nli and https://stanfordnlp.github.io/contract-nli/ | GitHub metadata CC-BY-4.0, research dataset of 607 English-language NDAs, 17 fixed hypotheses, entailment/contradiction/not-mentioned and evidence spans. Repo last pushed 2022-02-11. | **PILOT as evaluation methodology**, with attribution; never use as Brazilian statutory or jurisprudential ground truth. |

Additional code inspection (2026-10-30):
- **LexMCP:** `pyproject.toml` declares minimum-version dependencies with no comprehensive upper bounds. The inspected HTTP client implements timeouts, retries, rate limits and a TTL cache. The LexML client uses `follow_redirects=True`; before a pilot, validate redirect destinations and require a network egress allowlist. This is a code-pattern observation, not a penetration test.
- **datasets-jur:** `scripts/download_stj_academicos.sh` inserts remote CKAN JSON into an unquoted Python heredoc and derives download URLs and filenames from remote resource fields. It also references a hard-coded local workspace path and placeholder identifiers. `scripts/download_datajud.py` contains a March 2026 cutoff. Do not execute or integrate these scripts as-is; safely reimplement retrieval with strict host/path validation and independently verify data rights.

The GitHub license labels are preliminary code/dataset license metadata, not a full legal opinion on rights of third-party material, model weights, derived corpora, or downstream commercial use. No full code-security review, dependency SBOM, deployment or retrieval accuracy experiment has yet been performed on these candidates. No reviewed artifact should be silently marked APPROVE FOR PRODUCTION.

## Official-data feasibility

- [CNJ API Pública](https://www.cnj.jus.br/sistemas/datajud/api-publica/) describes public case-cover and movement **metadata**, not a reliable full-text holdings API. Do not use DataJud metadata to certify reasoning or case holdings.
- [CNJ DataJud Wiki](https://datajud-wiki.cnj.jus.br/api-publica/acesso/) documents publicly provided API-key authentication; rotation is possible. Use a current, officially obtained value and never hard-code it.
- [CNJ endpoints](https://datajud-wiki.cnj.jus.br/api-publica/endpoints/) are tribunal-specific aliases. Implement per-tribunal pagination, limits and retries.
- Priority for statutory text: current official publication from Planalto and applicable official gazettes; LexML for metadata/discovery with authoritative cross-checks.
- Priority for decisions: official STJ/STF or relevant tribunal **full text** with publication date, case number, legal proposition, passage and amended/overruled-state checks.
- Every result must distinguish **metadata discovered**, **document retrieved**, **passage matched**, **holding verified**, **temporal validity assessed**, **counter-authority investigated**, and **human reviewed**.

## Staged pilot contract

1. No confidential client material; only controlled synthetic inputs.
2. Read-only retrieval tools with explicit host allowlist, SSRF protection, scoped credentials, request budgets, caching rights and hard rate limits.
3. Ingestion must preserve original URLs, institution, retrieval timestamp, content digest, case/date, document version and evidence spans.
4. Separate authenticity, passage, applicability, validity and review flags. No single `VERIFIED` boolean.
5. Golden fixtures must be approved by independent qualified Brazilian counsel. Use distinct test/held-out sets, with false-positive and false-negative metrics.
6. Compare each adapter against direct official sources; record coverage, errors, p50/p95 latency, total run cost and exit/reversal conditions.
7. Require a signed-off dependency license list, SBOM, vulnerability scan, network/secret threat review and CI results before integrating.
8. Do not use these candidate datasets to imply OAB endorsement or a verified legal opinion.

## Build-versus-buy recommendation (provisional)

Begin with existing deterministic quote checks and official-source adapters owned by Gilberto. Use open-source retrieval libraries only through small, explicitly authorized interfaces. Consider a commercial full-text provider (including JUIT) **only** after measuring a documented completeness, licensing or reliability deficit that cannot economically be closed with the official-source strategy.

The relevant metric is fully verified and lawyer-accepted Brazilian legal analyses per unit of total cost, not search volume or token price. Costs and rights require current vendor terms and measured workload; no purchase is authorized by this document.

## Synthetic benchmark in this PR

`backend/benchmarks/contract_controls.py` probes a fictional commercial contract for an invented STJ citation, a 20% versus 2% penalty mismatch, unsupported representative authority, forum clause enforceability and a valid literal-extraction negative control. It exercises existing **deterministic** matching and evidence-status code. It does not call a model or verify Brazilian case law.

Acceptance: five expected control states and no implicit legal certification. Model accuracy, full-text source accuracy, lawyer ground truth and cross-model costs remain **NOT VERIFIED**.

## Independent release reviewers

**Engineering Audit Manager**: verify provenance schema, licensing, citation tests, security and synthetic fixture integrity. **DevOps Manager**: verify CI, network/secret boundaries, staging, repeatability and rollback. These are review responsibilities, not claims that autonomous manager processes are running.
