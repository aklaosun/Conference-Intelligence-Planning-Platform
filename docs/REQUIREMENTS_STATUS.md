# Project-plan alignment

Based on `Project_Plan_P26_T1.docx`, reviewed October 31, 2026. Assigned roles are not used to restrict implementation. This is an integrated prototype with additional planning features, not a claim of final project acceptance.

| Requirement | Current implementation / evidence | Remaining work |
| --- | --- | --- |
| Representative migrated real data | 35 CAC conferences/35 editions; workbook row/cell provenance; repeatable importer; no fabricated missing costs or dates | Receive CDSA source data and verify stale/inferred dates |
| Catalog and yearly history | Search/filter, conference/edition edits, source evidence, statuses, historical deadlines and prices | Broader multi-edition acceptance dataset |
| AI extraction and validation | Gemini, bounded official-page fetching, evidence validation, missing-field handling, change detection and staged suggestions | Sponsor evaluation of extraction accuracy across representative sites |
| Human Approve / Correct / Reject | Integrated evidence workbench; editable scalar/child rows; conflict decisions; atomic save; retained original response and reviewer audit | Sponsor acceptance walkthrough |
| Integrated frontend/backend | React/Vite served by Django; Electron Windows client; bundled local Python service; independent per-user data | Shared hosting deferred by user choice; macOS/Linux packaging |
| Access roles | Administrator, Viewer, Contributor and Coordinator; one-time, expiring/revocable invitations; server-enforced permissions; local-only automatic demo owner | Shared-account onboarding only after a shared host is chosen |
| Planning lifecycle | Configurable planning-stage table; edition owners, objectives and notes | Sponsor confirmation of workflow/status vocabulary and attendance authorization policy |
| Itemized costs | Registration/travel/lodging/other; estimated/actual amounts; source URLs; preserved unknowns; separate currency totals; inactive history | Sponsor budget rules and any approved currency conversion policy |
| Selection framework | Configurable center criteria/weights, explicit approval flag, source-backed 1–5 ratings; no score until all approved criteria are rated | Actual sponsor criteria, weight calibration and approval governance |
| Post-conference outcomes | Summary, counts, follow-ups, completed flag; report CSV includes actual cost-per-attendee/contact only when computable | Sponsor confirmation of outcome definitions and long-term history workflow |
| Deadline reminders | Dashboard upcoming window; upcoming/overdue/history views; source timezones and AoE retained; dated follow-ups | Per-user delivery preferences and exact timezone-aware notification scheduling |
| Reporting | Catalog CSV and planning/outcome CSV, known subtotals and missing counts; opt-in weekly email command with delivery records | SMTP/approved recipients/scheduler intentionally disabled in local demos |
| Discovery / monitoring | Existing bounded companion-page research and refresh command stage changes for human review | Autonomous discovery scope, configured schedules and operational monitoring |
| Normalized storage | Conference/edition, deadline/price, plans, budgets, criteria/ratings, outcomes, roles and access tables | Center flags/themes still use the existing boolean/JSON contract; migration to center/theme relationships remains pending |
| Testing / handoff | Existing extraction/review/import regression suite plus workspace auth/planning/report/local-bootstrap tests; desktop setup guide | Final acceptance tests, usability/accessibility review and live PostgreSQL validation |

## Acceptance conditions still requiring the sponsor

Obtain the actual RED/acceptance checklist, confirmed CAC/CDSA evaluation criteria and weights, definitions of a successful outcome, data verification rules, and a decision on shared access after the local demonstrations. These inputs are not inferred from developer assignments or invented to make a checklist appear complete.

## New data structures

`PlanningStage` configures workflow vocabulary. `ConferencePlan` is one per edition and records owner/objectives/notes. `BudgetLine` stores a currency and nullable decimal estimated/actual values; removed lines remain inactive. `SelectionCriterion` is scoped to CAC, CDSA or CCSE, with nullable weight and explicit approval. `CriterionRating` is unique per edition/criterion and records a rating and rationale. `OutcomeReport` is one per edition. `ActivityEvent` records workspace changes. `AccessInvitation` stores only the invitation token hash. `ReportSubscription` is disabled unless explicitly configured; `ReportDelivery` records the reporting week and sent time.
