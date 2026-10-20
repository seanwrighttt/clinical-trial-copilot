# Test fixtures

`studies_page.json` holds five real studies returned by the ClinicalTrials.gov
API v2 `/studies` endpoint on 2026-10-20, with `fields=protocolSection|hasResults`
and the default diabetes/obesity, Phase 2/3, interventional query. They were
picked to cover these cases:

| NCT ID      | Why it is included                                              |
|-------------|-----------------------------------------------------------------|
| NCT01074801 | Completed; `yyyy-MM` partial dates; start date has no type      |
| NCT03919929 | Completed; combined PHASE2/PHASE3; has results                  |
| NCT03554200 | Terminated, with `whyStopped`                                   |
| NCT07521631 | Recruiting; ESTIMATED completion dates; no detailed description |
| NCT01285934 | Withdrawn; PHASE1/PHASE2; partial dates; zero enrollment        |

Trimming: the studies came from several requests (one per status) and were put
into a single page object without `nextPageToken`. Each study's
`contactsLocationsModule` was removed, since the parser does not use it. All
other content is unchanged.
