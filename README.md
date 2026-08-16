# football_news — Project Map

> Central reference for the football_news project.
> This file is the source of truth for project architecture, workflows,
> database responsibilities, development status, decisions, and roadmap.

**Last reviewed:** 2026-08-17  
**Repository:** `youssef0megahed/football_news`  
**Default branch:** `main`  
**Supabase project:** `football_news`  
**Supabase Project ID:** `ofsxxmfhkotqunjyafvo`

---

# 1. Project Goal

Build an automated football information and news platform centered around football matches, news collection, AI processing, and social publishing.

The project uses:

- GitHub
- GitHub Actions
- Python
- football-data.org
- Supabase PostgreSQL
- Telegram
- Future AI processing
- Future Facebook/social publishing

The system is intentionally divided into independent workflows to prevent code overlap and make debugging easier.

---

# 2. Core Architecture

```text
                    football-data.org
                           │
                           ▼
                    fixtures.py
                           │
                           ▼
                  Supabase PostgreSQL
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            ▼            ▼
        competitions     teams        matches
                                         │
                         ┌───────────────┼───────────────┐
                         │               │               │
                         ▼               ▼               ▼
                   match_events   match_news_state    news
                                                         │
                                                         ▼
                                                  AI Processing
                                                         │
                                          ┌──────────────┴──────────────┐
                                          ▼                             ▼
                                      Telegram                      Facebook

The current repository implements only part of this architecture.


---

3. Repository Structure

football_news/
│
├── .github/
│   └── workflows/
│       ├── fixtures.yml
│       └── news_fixtures.yml
│
├── src/
│   ├── fixtures.py
│   └── news_fixtures.py
│
└── PROJECT_MAP.md


---

4. Workflow Map

4.1 Fixtures Workflow

.github/workflows/fixtures.yml
                │
                ▼
        src/fixtures.py
                │
                ▼
       football-data.org
                │
                ▼
           Supabase
                │
        ┌───────┼───────┐
        ▼       ▼       ▼
 competitions teams   matches

Responsibility

fixtures.py is responsible for football-data ingestion.

It should handle:

Competitions

Teams

Fixtures

Match status

Scores

Kickoff times

Team synchronization

Match synchronization


Current leagues

Premier League     PL
La Liga             PD
Serie A             SA
Bundesliga          BL1
Ligue 1             FL1

Schedule

Current GitHub Action schedule:

30 * * * *

Meaning approximately once every hour at minute 30.

It also supports manual execution.


---

5. Match News / Telegram Workflow

.github/workflows/news_fixtures.yml
                │
                ▼
        src/news_fixtures.py
                │
                ▼
             Supabase
                │
                ▼
          Match information
                │
                ▼
        Arabic Telegram message
                │
                ▼
             Telegram
                │
                ▼
          news_events

Responsibility

This workflow currently handles match-related Telegram notifications.

It should NOT become responsible for:

Football data ingestion

General news collection

AI processing

Facebook publishing

Match event ingestion


Those should remain separate workflows.


---

6. Database

Current Supabase tables:

competitions
teams
matches
match_events
match_news_state
news
news_events


---

7. Database Relationships

competitions
     │
     │ 1:N
     ▼
   matches
   │    │
   │    ├──────────────► match_events
   │    │
   │    ├──────────────► match_news_state
   │    │
   │    └──────────────► news
   │
   ├── home_team_db_id ──► teams
   │
   └── away_team_db_id ──► teams


---

8. competitions

Purpose

Stores football competitions/leagues.

Important fields

id
name
code
country
source
created_at
updated_at

Current data

5 competitions


---

9. teams

Purpose

Stores football teams.

Important fields

id
source
source_team_id
name
short_name
tla
country
crest_url
name_ar
league
created_at
updated_at

Important rule

Team identity from the external source is:

(source, source_team_id)

Current data

96 teams


---

10. matches

Purpose

Canonical match/fixture records.

Important fields

id
source
source_match_id
competition_id
competition_name
season
kickoff_utc
kickoff_local
timezone
home_team_id
home_team_name
away_team_id
away_team_name
status
home_score
away_score
venue
last_updated_at
home_team_db_id
away_team_db_id
created_at
updated_at

Important rule

Match identity from the external source is:

(source, source_match_id)

Current data

5 matches


---

11. match_events

Purpose

Stores detailed events occurring during matches.

Expected examples:

GOAL
YELLOW_CARD
RED_CARD
SUBSTITUTION
PENALTY
OWN_GOAL

Important fields

id
match_id
source
source_event_key
event_type
minute
extra_time
team_id
team_name
player
assist
card
home_score
away_score
raw_event
created_at
updated_at

Current status

🔴 Not active

Current database:

0 rows

Important history

A match-events implementation was previously experimented with but was removed.

Do NOT blindly recreate the old implementation.

Before rebuilding it:

1. Decide the data source.


2. Decide the event schema.


3. Decide event uniqueness.


4. Decide whether events are immutable.


5. Create a dedicated workflow.




---

12. match_news_state

Purpose

Stores the current notification state of a match.

Important fields:

id
match_id
last_status
last_home_score
last_away_score
initialized
updated_at

Current status

🟡 Exists but architecture needs review

Important issue

The current Telegram workflow primarily uses news_events to detect previously sent notifications.

Therefore we currently have two concepts:

match_news_state
        +
news_events

Before expanding notification logic, decide exactly which table owns:

Current state

Historical events

Duplicate prevention


Do not create a third state mechanism.


---

13. news

Purpose

General football news storage.

The table is designed for a broader news pipeline.

Important fields include:

id
match_id
news_type
title
content
source
source_article_id
original_title
arabic_title
summary
arabic_summary
image_url
category
league
team_id
team_name
player_name
status
relevance_score
ai_processed
ai_processed_at
telegram_sent
telegram_sent_at
telegram_message_id
facebook_sent
facebook_sent_at
created_at
updated_at

Current data

21 rows

Important architecture

news is for GENERAL NEWS.

It should not be confused with:

news_events

which currently represents match notification events.


---

14. news_events

Purpose

Historical record of match notification messages.

Important fields:

id
match_id
message_type
status
home_score
away_score
created_at

Current data

10 rows

Current usage

news_fixtures.py uses this table to prevent duplicate match notifications.

Future consideration

Evaluate whether:

news_events.match_id

should have a foreign key to:

matches.id

before expanding the event architecture.


---

15. Current Database Snapshot

Last reviewed:

competitions      5
teams            96
matches           5
match_events      0
match_news_state  3
news             21
news_events      10


---

16. Current Project Status

Legend:

🟢 Working
🟡 Exists but needs validation
🔴 Not implemented / stopped
⚪ Planned

Component	Status

football-data.org ingestion	🟢
Competition synchronization	🟢
Team synchronization	🟢
Match synchronization	🟢
Cairo timezone handling	🟢
Fixtures GitHub workflow	🟢
Match Telegram notifications	🟢
Duplicate notification prevention	🟢/🟡
match_news_state	🟡
Match events ingestion	🔴
General news collector	🔴
AI processing	⚪
Facebook publishing	⚪
General-news Telegram publishing	⚪
Full social publishing system	⚪



---

17. Development History

The project has gone through several experiments.

Important observed history:

fixtures.py has been repeatedly improved.

news_fixtures.py has been repeatedly improved.

news.py was renamed to news_fixtures.py.

Match-event fetching was experimented with.

A test script for match events was added and later deleted.

news_collector.py existed and was later deleted.

Workflow files were renamed/refined several times.


Important rule

Deleted experimental code should NOT automatically be restored.

First determine:

Why was it created?
Why was it changed?
Why was it deleted?
What problem did it have?

Then implement the clean version.


---

18. Workflow Separation Rules

This is one of the most important sections of the project.

Fixtures

Responsible for:

football-data.org
        ↓
competitions
teams
matches

Match Events

Future dedicated workflow.

Responsible for:

football-data source
        ↓
match_events

Match Notifications

Responsible for:

matches / match state
        ↓
Telegram
        ↓
notification history

General News

Future dedicated workflow.

Responsible for:

news sources
        ↓
news

AI

Future dedicated workflow.

Responsible for:

news
 ↓
AI processing
 ↓
Arabic content
 ↓
relevance

Social Publishing

Future dedicated workflows.

Responsible for:

news
 ↓
Telegram
Facebook


---

19. Security Rules

Never hard-code secrets.

Secrets include:

FOOTBALL_DATA_TOKEN
SUPABASE_URL
SUPABASE_KEY
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID

Use:

GitHub Actions Secrets

or environment variables.

Never commit secrets into:

.py
.yml
.md
.json


---

20. Timezone Standard

Project timezone:

Africa/Cairo

External football timestamps should be handled carefully.

Recommended concept:

UTC
 ↓
stored canonical timestamp
 ↓
Africa/Cairo presentation

Never rely on the GitHub runner's local timezone.


---

21. Idempotency Rules

Every ingestion workflow should be safe to run multiple times.

External IDs must be preserved.

Examples:

Team:
(source, source_team_id)

Match:
(source, source_match_id)

Event:
(source, source_event_key)

The same external entity should never create duplicate internal records.


---

22. Roadmap

Phase 1 — Stabilize Foundation

[✓] Fixtures ingestion
[✓] Team synchronization
[✓] Match synchronization
[✓] Telegram match notifications
[ ] Finalize notification-state architecture
[ ] Improve logging/error reporting

Phase 2 — Match Events

[ ] Select event data source
[ ] Build dedicated event workflow
[ ] Implement event ingestion
[ ] Implement idempotency
[ ] Validate goals/cards/substitutions

Phase 3 — Match Notifications

[ ] Define notification types
[ ] Finalize match state model
[ ] Finalize news_events model
[ ] Prevent duplicate messages robustly

Phase 4 — General News

[ ] Build news collector
[ ] Normalize article IDs
[ ] Store original articles
[ ] Handle duplicates

Phase 5 — AI

[ ] AI relevance scoring
[ ] Arabic title generation
[ ] Arabic summary generation
[ ] AI failure/retry handling

Phase 6 — Social Publishing

[ ] Telegram general news
[ ] Facebook publishing
[ ] Per-channel delivery state
[ ] Retry system
[ ] Idempotent publishing


---

23. Open Architecture Decisions

Before implementing the related systems, answer:

1. match_news_state

Do we still need it?

Or should:

news_events

be the notification history while:

match_news_state

stores only current state?


---

2. news_events

Should:

news_events.match_id

have a foreign key to:

matches.id

?


---

3. Match Events Source

What source should provide:

goals
cards
substitutions
penalties

?


---

4. News Lifecycle

Define the lifecycle of a news article.

Example:

NEW
 ↓
AI_PROCESSING
 ↓
PROCESSED
 ↓
TELEGRAM
 ↓
FACEBOOK


---

5. Workflow Dependencies

Should workflows remain independent?

Or should some workflows depend on previous workflows?

Example:

fixtures
   ↓
match_events
   ↓
notifications

This should be explicit.


---

24. Conversation Map

The project is intentionally divided into specialized conversations.

Main / Control Center

Responsible for:

Architecture
Database overview
Roadmap
Cross-workflow decisions
Project Map
Integration

This conversation should NOT become the place where every workflow's implementation code is mixed together.


---

Fixtures Conversation

Responsible for:

src/fixtures.py
.github/workflows/fixtures.yml


---

Match Events Conversation

Responsible for:

Future match-events workflow
match_events


---

Match News / Telegram Conversation

Responsible for:

src/news_fixtures.py
.github/workflows/news_fixtures.yml
news_events
match notifications


---

General News Conversation

Responsible for:

Future news collector
news table


---

AI Conversation

Responsible for:

AI processing
Arabic content
relevance scoring


---

Social Publishing Conversation

Responsible for:

Telegram general news
Facebook
publishing state


---

25. Project Development Rules

1. One workflow = one clear responsibility.


2. Do not mix workflows unnecessarily.


3. Do not change database schema without understanding existing constraints.


4. Do not duplicate existing functionality.


5. Check GitHub before recreating old code.


6. Check Supabase before changing database behavior.


7. Keep external IDs separate from internal database IDs.


8. Keep secrets out of source code.


9. Make ingestion idempotent.


10. Use Africa/Cairo consistently for local football presentation.


11. Document important architecture decisions.


12. Update this file after meaningful architecture changes.


13. Do not restore deleted experimental code blindly.


14. Every new workflow must have a clearly defined owner and purpose.


15. Every production workflow should have logging and an understandable failure mode.




---

26. Change Log

2026-08-17

Initial PROJECT_MAP.md created.

Audited:

GitHub repository

Repository structure

GitHub Actions workflows

Python entrypoints

Supabase tables

Database relationships

Current row counts

Existing match/news architecture

Historical experiments visible in Git history


Initial architectural concerns identified:

match_news_state vs news_events

Empty match_events

Deleted news_collector.py

Deleted match-event experiments

Separation between general news and match notifications



---

27. Maintenance Rule

This file is a living document.

Whenever one of the following changes:

Repository structure
Workflow
Database schema
API source
Architecture
Feature status
Publishing system
AI pipeline

update PROJECT_MAP.md.

The goal is:

GitHub
   +
Supabase
   +
PROJECT_MAP.md
   =
Complete project reference
