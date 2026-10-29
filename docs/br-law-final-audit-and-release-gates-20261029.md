# Brazilian-law audit — release verification and evidence requirements (2026-10-29)

## Existing automated findings and limits

The ten-PR remediation chain (#55-#64) implements automatic controls: BR-only jurisdiction, deterministic supplied-document quote matching, official-domain classification without case authentication, claim-level unverified provenance, explicitly unverified final conclusions, provider token usage, predispatch worst-case cost limits when valid rates configured, preflight cost-plan metadata, private admin operational summaries and a versioned synthetic control corpus. These controls are **NOT** proof of Brazilian legal accuracy.

**Held-out legal accuracy baseline: unknown**. **Legal proposition correctness: unknown**. **Citation validity across live STJ/STF/CVM/CADE sources: unknown**. **Expert reasoning score: unknown**. **Cost per verified legal conclusion: unknown**. Do not replace missing values with zero or PR passing percentages.

## Human reviewer operating protocol

1. Qualified Brazilian lawyers independently select at least 30 legal scenarios and update gold references from official primary authorities as of the relevant fact/date. Cover federal civil, procedural, labor, corporate, regulatory, state/municipal where legally applicable. Obtain source rights/usage permissions and avoid confidential client data.
2. Separately score source authenticity, binding effect, correct statute version, issue recall/precision, IRAC/CREAC applicability, counterarguments and harmful unsupported claims. Record reviewer identifiers and agreement/disagreement adjudication without exposing client information.
3. Freeze evaluation cases BEFORE tuning. Keep development and held-out partitions, source snapshots, evaluator rubric version and citations. Run exactly the same corpus with single-agent and Gilberto full/focused review variants, controlling model/version, date and reference inputs.
4. Compute claim-level precision/recall, citation accuracy, unsupported rate, costs per accepted finding, tokens, p50/p95 latencies, catastrophic legal-error counts and uncertainty calibration, using provider metering and invoices when available.
5. No production promotion if critical failures remain or independent lawyer reviewer approval is absent. CI-green or model consensus never satisfies this gate. Do not deploy current branched changes over original insecure production before resolving original security PR dependencies.

## Source acquisition/licensing constraints

The primary source-entrypoints are Planalto (legislation), STF jurisprudence, STJ SCON official decisions, CVM rules and decisions, CADE jurisprudence and CNJ DataJud metadata. A case number or DataJud metadata is not an authenticated holding. CNJ Portaria 160/2020 as amended in 2026 imposes restrictions on commercial modification/distribution of API data, per official text: https://atos.cnj.jus.br/atos/detalhar/3453. Review authorizations before programmatic collection. No live external legal ingestion was added in these ten PRs because authoritative API rights and source-validation requirements remain unverified.

## Competitor reference (vendor claims, not head-to-head testing)

Harvey promotes regional legal knowledge sources: https://help.harvey.ai/topics/knowledge-sources ; Thomson Reuters CoCounsel describes Westlaw/Practical Law evidence-linked research: https://legal.thomsonreuters.com/en/legal/research-corp ; LexisNexis Protégé and Vincent AI are evaluation candidates only (licensed legal content access not granted here). No test conditions permit honest claims that Gilberto outperforms them on Brazilian legislation or case law.

## Controlled implementation ledger

| Wave | GitHub PRs | Goal | Validation |
|---|---|---|---|
| 1 — Brazilian legal controls | #55 #56 #57 #58 #59 | Jurisdiction, quotes, source provenance, claims, qualified review warning | Deterministic control tests; *not* lawyer-verified accuracy |
| 2 — Financial discipline | #60 #61 #62 | Provider usage, hard estimated cap, cost preview | Mocked usage and pricing arithmetic; invoices unverified |
| 3 — Operations and governance | #63 #64 | Admin safe metrics, versioned BR corpus and CI gate | Synthetic tests; staging and human sign-off pending |

**Current release ledger, 29 October 2026:** PRs #55-#65 and #68 were merged into the staging-only integration branch `release/brlaw-security-staging-20261029`. The source tree at `b97150b01d7d059f9c7910f66ef2d67d89a3b57b` matched the GitHub CI-passing candidate and was deployed with `SUCCESS` status to **both Railway staging services** (backend deployment `09d88313-6b95-4d86-8119-98a89d84ad07`; frontend `146a9299-59f4-48fb-8407-5db68fd10413`). The backend readiness and frontend health checks both returned 200. PR #67 was closed without merge as a duplicate of #58/#59; missing checkpoint persistence was fixed by #68.

**Production remains unchanged** at `main` SHA `18f61dae499c6d07e72e3bbc8084beb91e26b533`. The staging branch contains draft prerequisite security/recovery code from #39-#54 that has not been promoted to production; do not merge that history into main without completing release gates. CI passing does not prove lawyer-scored legal correctness.

**Release blockers:** no qualified Brazilian-lawyer-adjudicated accuracy corpus or legal reasoning scores; no live authenticated verification of official STJ/STF/CVM/CADE holdings; no measured provider invoice-based cost per verified conclusion; no completed two-user staging legal-workflow isolation and final independent backup restore sign-off. Staging is for synthetic/nonconfidential test materials only. Cost caps are estimated and inactive by default unless validated input/output prices and cap are configured.


## Additional external benchmark evidence reviewed

- **LegalBench-BR**, Pedro Barbosa de Carvalho Neto, 2026, https://arxiv.org/abs/2604.18878 — reproducible **Brazilian judicial legal-area classification** benchmark. It tests document classification, not correctness of legal opinions, case-law citation authenticity or M&A contract interpretation. Do not import reported classification accuracy as Gilberto's legal-reasoning score. Check the dataset's DataJud provenance and redistribution permissions before processing.
- **LegalBench-RAG**, Nicholas Pipitone & Ghita Houir Alami, 2024, https://arxiv.org/abs/2408.10343 — legal retrieval evaluation methodology emphasizing narrow, human-annotated evidence spans. The corpus is not an independently certified Brazilian-law accuracy test.
- **Harvey knowledge sources**, https://help.harvey.ai/topics/knowledge-sources — vendor-published jurisdiction-specific research integration. **Lexis+ Protégé**, https://www.lexisnexis.com/en-us/products/lexis-plus-protege/legal-research.page — vendor describes linked legal research and Shepard's citations. Neither is an independently measured comparison with Gilberto in Brazilian legal workflows.

A credible comparative study must use an agreed Brazilian-law evaluation date, independently retrieved permitted legal texts, a frozen held-out set, blind expert scoring, matched model budgets and public reporting of unsuccessful/uncertain outputs. Product materials and general legal NLP classification leaderboards are not substitute evidence.
