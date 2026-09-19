# Hangout Planner Agent

## Setup
1. `cd backend`
2. `python -m venv .venv` and activate it
3. `pip install -r requirements.txt`
4. `cp .env.example .env` and fill in `GEMINI_API_KEY` (from
   [Google AI Studio](https://aistudio.google.com/apikey)). Leave
   `MOCK_MODE=true` to run everything without touching real Calendar/Gmail.
5. In Google Cloud Console, open your OAuth client (type **Web application**)
   and add this exact redirect URI:
   `http://localhost:8000/oauth2callback`
   Put that client's ID/secret into `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`
   in `.env`.
6. `python main.py` (or `uvicorn main:app --reload --port 8000`) - runs on
   `http://localhost:8000`.

## Using the web app
- Open `http://localhost:8000/` - anyone who can reach this port can create a
  group (group name, their own name + email, and a required location like
  "Koramangala, Bangalore" - just specific enough to geocode).
- Creating a group redirects to `/groups/{id}` - bookmark it, it's your
  group's dashboard.
- The dashboard shows a shareable join link (`/groups/{id}/join`). Anyone who
  opens it and submits their name + email + location is added to the group -
  no approval step, so treat the link like an invite.
- The dashboard's "Plan something" form lets any member ask the agent to plan
  a hangout for a specific day, with an optional free-text note (constraints,
  vibe, etc.). Submitting it kicks off a run; the response (and a per-member
  reply box, for negotiating) shows up under "Runs".
- Replying as a given person feeds that reply back into the *same*
  negotiation session, so the agent can re-propose or escalate - it decides,
  nothing is hardcoded.

## Connecting your Google account
Visit `http://localhost:8000/oauth2/login` in a browser once. It redirects
to Google's consent screen (Calendar read + Gmail send scopes), then back to
`/oauth2callback`, which saves a refreshable token to
`data/google_token.json` (gitignored - never commit it). After that, set
`MOCK_MODE=false` to make `get_calendar_freebusy` and `send_email` use the
real APIs instead of mock data.

Note: this OAuth flow authorizes *one* Google account - whoever is hosting
the server. All groups' calendar checks and outgoing emails go through that
one account. Its Calendar API access only sees calendars that account can
see, so real per-member calendar checks only work for members who've shared
their calendar with the host account (there's no per-member OAuth here).

## Location-aware planning
Every member types a location when they create or join a group (city/area is
enough, e.g. "Koramangala, Bangalore" - it just needs to be specific enough
to geocode). The agent has two tools for this:
- `get_member_locations` - reads those locations back; anyone who left it
  blank shows as `"unknown"`.
- `find_nearby_places` - a real venue search (e.g. "restaurants" near a
  member's location) so a food hangout names an actual nearby restaurant
  instead of a vague or made-up suggestion.

`find_nearby_places` needs no API key and no billing - it geocodes the
location text with **OpenStreetMap's Nominatim** and searches for named
venues with the matching category via **OpenStreetMap's Overpass API**, both
free public services. When `MOCK_MODE=true` it returns quick mock venue
names instead (same pattern as everything else); real search only needs
`MOCK_MODE=false`. Since these are shared public services with real rate
limits (~1 request/second), they're fine at this app's scale but not meant
for production traffic.

The system prompt explicitly tells the agent to only use location text that
actually came from `get_member_locations`, to only name a venue that
actually came back from `find_nearby_places`, and to say so plainly (not
invent a city or restaurant) when a member has no location on file or the
search comes back empty.

Picking a location that's fair to a spread-out group, and deciding which
category of venue fits the request, is left to the agent's judgment - same
philosophy as everything else it does.

## Files
- `main.py` - the web app: group create/join/dashboard pages and the
  plan/reply actions, plus the OAuth routes
- `groups.py` - group data model (members, past runs) persisted as one JSON
  file per group under `data/groups/<id>/`
- `agent/context.py` - a `ContextVar` carrying the current request's
  `group_id` down into the skill implementations, so the LLM's tool schemas
  don't need a `group_id` argument
- `agent/agent.json` - agent identity, model, system prompt, and the loop's
  termination rule
- `agent/skills/*.json` - one manifest per tool: name, description, JSON
  input schema, and which Python function implements it
- `agent/loop.py` - loads `agent.json` + the skill manifests and runs the
  Gemini tool-use loop against them
- `skills_impl/*.py` - the actual implementations (mocked calendar/weather/
  history/email by default, controlled by `MOCK_MODE`), scoped to whichever
  group is currently in `agent/context.py`
- `skills_impl/google_oauth.py` - the OAuth flow + token storage shared by
  the calendar and Gmail skills
- `skills_impl/locations.py`, `skills_impl/places.py` - member locations and
  the free OpenStreetMap-backed venue search, both mockable via `MOCK_MODE`
- `templates/*.html`, `static/style.css` - the (server-rendered, no JS
  framework) web UI
- `data/groups/<id>/group.json` - that group's name, members, and run history
- `data/groups/<id>/past_plans.json` - that group's hangout history, used for
  the fairness/recency judgment call
- `data/groups/<id>/sessions/*.json` - one saved conversation per kickoff, so
  a later reply can resume the same negotiation
- `data/google_token.json` - the host's saved OAuth token (created after
  visiting `/oauth2/login`; gitignored)

## Triggering it on a schedule
Nothing stops a member from also calling `POST /groups/{id}/plan` (form
fields `date`, `note`) from a scheduler (OS cron, GitHub Actions, or
APScheduler inside `main.py`) instead of the web form, if you want a
standing weekly nudge in addition to on-demand requests.

## If the Gemini model name stops working
Google renames/retires Gemini models fairly often. If `GEMINI_MODEL` in
`.env` starts erroring, check the current model IDs at
https://ai.google.dev/gemini-api/docs/models and update it there.
