# Build Log

## Commit: Add capstone plan and build log

- Date: 2026-09-11
- Time spent: ~[45] minutes
- Rough tokens used: ~[X]
- What shipped:
  - Defined the capstone problem
  - Defined the target users
  - Defined the MVP scope
  - Defined the final goals
  - Defined the AI involvement level
  - Created the initial build log

## Commit: Finalize capstone plan and build log

- Date: 2026-09-11
- Time spent: ~[45] minutes
- Rough tokens used: ~[X]
- What shipped:
  - Refined the capstone scope
  - Clarified the MVP and final goals
  - Added the AI-involvement rationale
  - Corrected the plan filename to plan.md
  - Updated the build log## 2026-09-11 16:16:54
- **Message:** Clean up build log with development history
- **Author:** Krishiv Vijayakumar
- **Files changed:**
  - BUILD_LOG.md

## 2026-09-11 16:18:16
- **Message:** addition to agentic plan
- **Author:** Krishiv Vijayakumar
- **Files changed:**
  - BUILD_LOG.md
  - plan.md

## 2026-09-17 15:31:04
- **Message:** save commit
- **Author:** Krishiv Vijayakumar
- **Files changed:**
  - BUILD_LOG.md

## 2026-09-17 15:59:19
- **Message:** 
- **Author:** Krishiv Vijayakumar
- **Files changed:**
  - BUILD_LOG.md

## 2026-09-17 15:59:40
- **Message:** changed plan
- **Author:** Krishiv Vijayakumar
- **Files changed:**
  - BUILD_LOG.md

## 2026-09-17 16:00:07
- **Message:** save commit
- **Author:** Krishiv Vijayakumar
- **Files changed:**
  - BUILD_LOG.md

## Commit: Build the hangout-planner agent, web app, and location-aware planning

- Date: 2026-09-17
- Time spent: ~2 hours 35 minutes (16:00-18:35, per session/commit timestamps)
- Rough tokens used: ~150,000-300,000 (Claude Code doesn't expose an exact
  cumulative counter for a session; this is a rough order-of-magnitude
  estimate from conversation length and tool-call volume, not a precise
  measurement)
- What shipped:
  - Defined the agent as `agent/agent.json` (identity, model, system prompt,
    loop/termination rules) plus one JSON manifest per tool under
    `agent/skills/`, matching the MVP tool list from the capstone plan
  - Built the Gemini tool-use loop (`agent/loop.py`) and the skill
    implementations (`skills_impl/`) for calendar free/busy, weather, hangout
    history, member locations, nearby-venue search, and email
  - Switched the underlying model from Claude to Gemini (`google-genai`),
    fixing a function-calling role bug (`role="tool"` isn't valid; needs
    `"user"`) and working around model deprecation/quota limits along the way
  - Added real Google OAuth (Calendar read + Gmail send) via a
    Web-application OAuth client, including fixing a PKCE `code_verifier`
    bug that broke the login callback
  - Turned the single-roster prototype into a real multi-group web app
    (FastAPI + Jinja2): anyone can create a group, share a join link, and
    ask the agent to plan something for a specific day; replies feed back
    into the same negotiation session so the agent can re-propose or
    escalate on its own judgment
  - Added location-aware planning: every member enters a location, and the
    agent grounds venue suggestions (e.g. "food" -> real nearby restaurants)
    using free OpenStreetMap geocoding + search - no Google Maps billing
    account required
  - Hardened error handling: friendly in-app messages for Gemini
    quota/API errors instead of raw 500s, plus automatic retry on transient
    503s

## 2026-09-17 18:31:26
- **Message:** first prototype agent
- **Author:** Krishiv Vijayakumar
- **Files changed:**
  - BUILD_LOG.md

## 2026-09-17 18:31:39
- **Message:** 
- **Author:** Krishiv Vijayakumar
- **Files changed:**
  - .gitignore
  - BUILD_LOG.md
  - backend/.env.example
  - backend/.gitignore
  - backend/README.md
  - backend/agent/__init__.py
  - backend/agent/agent.json
  - backend/agent/context.py
  - backend/agent/loop.py
  - backend/agent/skills/find_nearby_places.json
  - backend/agent/skills/get_calendar_freebusy.json
  - backend/agent/skills/get_member_locations.json
  - backend/agent/skills/get_past_plans.json
  - backend/agent/skills/get_weather.json
  - backend/agent/skills/send_email.json
  - backend/groups.py
  - backend/main.py
  - backend/requirements.txt
  - backend/skills_impl/__init__.py
  - backend/skills_impl/calendar_skill.py
  - backend/skills_impl/email.py
  - backend/skills_impl/google_oauth.py
  - backend/skills_impl/locations.py
  - backend/skills_impl/past_plans.py
  - backend/skills_impl/places.py
  - backend/skills_impl/weather.py
  - backend/static/style.css
  - backend/templates/base.html
  - backend/templates/group.html
  - backend/templates/index.html
  - backend/templates/join.html

## 2026-09-17 18:31:55
- **Message:** Build hangout-planner agent, web app, and location-aware planning
- **Author:** Krishiv Vijayakumar
- **Files changed:**
  - .gitignore
  - BUILD_LOG.md
  - backend/.env.example
  - backend/.gitignore
  - backend/README.md
  - backend/agent/__init__.py
  - backend/agent/agent.json
  - backend/agent/context.py
  - backend/agent/loop.py
  - backend/agent/skills/find_nearby_places.json
  - backend/agent/skills/get_calendar_freebusy.json
  - backend/agent/skills/get_member_locations.json
  - backend/agent/skills/get_past_plans.json
  - backend/agent/skills/get_weather.json
  - backend/agent/skills/send_email.json
  - backend/groups.py
  - backend/main.py
  - backend/requirements.txt
  - backend/skills_impl/__init__.py
  - backend/skills_impl/calendar_skill.py
  - backend/skills_impl/email.py
  - backend/skills_impl/google_oauth.py
  - backend/skills_impl/locations.py
  - backend/skills_impl/past_plans.py
  - backend/skills_impl/places.py
  - backend/skills_impl/weather.py
  - backend/static/style.css
  - backend/templates/base.html
  - backend/templates/group.html
  - backend/templates/index.html
  - backend/templates/join.html

## 2026-09-17 18:35:27
- **Message:** Fill in time/tokens estimates for the last build log entry
- **Author:** Krishiv Vijayakumar
- **Files changed:**
  - BUILD_LOG.md

## 2026-09-19 17:17:54
- **Message:** UI reskin
- **Author:** Krishiv Vijayakumar
- **Files changed:**
  - BUILD_LOG.md

## 2026-09-19 17:18:27
- **Message:** UI reskin
- **Author:** Krishiv Vijayakumar
- **Files changed:**
  - BUILD_LOG.md

## 2026-09-19 17:18:54
- **Message:** ui
- **Author:** Krishiv Vijayakumar
- **Files changed:**
  - BUILD_LOG.md

## 2026-09-19 17:19:59
- **Message:** ui
- **Author:** Krishiv Vijayakumar
- **Files changed:**
  - BUILD_LOG.md

## 2026-09-19 17:21:38
- **Message:** ui
- **Author:** Krishiv Vijayakumar
- **Files changed:**
  - BUILD_LOG.md
  - backend/.env.example
  - backend/agent/agent.json
  - backend/agent/context.py
  - backend/agent/skills/find_nearby_places.json
  - backend/agent/skills/get_favorite_spots.json
  - backend/agent/skills/get_member_preferences.json
  - backend/agent/skills/send_email.json
  - backend/data/geocode_cache.json
  - backend/groups.py
  - backend/main.py
  - backend/skills_impl/email.py
  - backend/skills_impl/favorites.py
  - backend/skills_impl/geocoding.py
  - backend/skills_impl/places.py
  - backend/skills_impl/preferences.py
  - backend/static/app.js
  - backend/static/favicon.ico
  - backend/static/favicon.svg
  - backend/static/style.css
  - backend/templates/_circle.html
  - backend/templates/_flow.html
  - backend/templates/base.html
  - backend/templates/favorites.html
  - backend/templates/group.html
  - backend/templates/index.html
  - backend/templates/join.html
  - backend/templates/preferences.html
  - backend/templates/respond.html
  - backend/templates/vote.html
  - backend/utils/__init__.py
  - backend/utils/response_token.py
  - plan.md

s11## 2026-09-19 17:23:20
- **Message:** ui
- **Author:** Krishiv Vijayakumar
- **Files changed:**
  - BUILD_LOG.md

## 2026-09-19 17:23:39
- **Message:** uuuu
- **Author:** Krishiv Vijayakumar
- **Files changed:**
  - BUILD_LOG.md

## 2026-09-19 17:32:56
- **Message:** git ignore
- **Author:** Krishiv Vijayakumar
- **Files changed:**
  - BUILD_LOG.md
  - backend/.gitignore

## 2026-09-19 17:40:18
- **Message:** Remove leaked Google Places API key from .env.example
- **Author:** Krishiv Vijayakumar
- **Files changed:**
  - BUILD_LOG.md
  - backend/.env.example

## 2026-09-19 17:40:37
- **Message:** Log security-fix commit in BUILD_LOG.md
- **Author:** Krishiv Vijayakumar
- **Files changed:**
  - BUILD_LOG.md

## 2026-09-19 17:40:52
- **Message:** Log build-log commit in BUILD_LOG.md
- **Author:** Krishiv Vijayakumar
- **Files changed:**
  - BUILD_LOG.md

## 2026-09-19 17:41:04
- **Message:** Merge branch 'assesment-2-krishiv' of https://github.com/Turtlesalt/Krishiv-Capstone into assesment-2-krishiv
- **Author:** Krishiv Vijayakumar
- **Files changed:**

## 2026-09-19 17:41:49
- **Message:** Merge origin/assesment-2-krishiv, resolve build-log conflict
- **Author:** Krishiv Vijayakumar
- **Files changed:**
  - BUILD_LOG.md

## 2026-09-19 17:42:03
- **Message:** Log merge commit in BUILD_LOG.md
- **Author:** Krishiv Vijayakumar
- **Files changed:**
  - BUILD_LOG.md

## Commit: Fix recommendation personalization bugs, add theme toggle, rebalance UI colors

- Date: 2026-09-24
- Time spent: ~3-4 hours (spans a diagnostic investigation with real session-log
  tracing, two backend fixes with scripted verification against the real code
  and data, and a full UI color audit/implementation/browser verification)
- Rough tokens used: ~350,000-550,000 (Claude Code doesn't expose an exact
  cumulative counter for a session; this is a rough order-of-magnitude
  estimate from conversation length and tool-call volume, not a precise
  measurement)
- What shipped:
  - Diagnosed why emailed venue recommendations ignored favorites/preferences:
    traced the live Gemini tool-calling path (there's no separate "assemble
    options" function - the model itself orchestrates
    get_member_preferences/get_favorite_spots/find_nearby_places/send_email)
    using a real historical session log plus a scratch-copied data dir to
    reproduce it safely
  - Fixed `get_favorite_spots` (skills_impl/favorites.py) silently returning
    zero favorites whenever called with the plural category form
    ("restaurants") that its own tool schema documents - the singular/plural
    normalization now lives in one shared `groups.favorite_category_matches`,
    used by both `get_favorite_spots` and `find_nearby_places`'s internal
    favorites lookup, so it can't diverge into two copies again
  - Fixed `find_nearby_places` (skills_impl/places.py) discarding
    already-computed favorites/preference matches whenever the Overpass API
    timed out - it now degrades to a favorites/preference-only result with an
    explanatory note instead of a bare error that forced the agent into
    ever-more-generic retries
  - Centralized data-directory resolution in new `backend/paths.py` (DATA_DIR
    from env, defaulting to ./data) and pointed groups.py/geocoding.py/
    google_oauth.py at it, so a mounted volume path works the same everywhere
  - Added the light/dark theme toggle (base.html header button + app.js click
    handler + localStorage persistence, with a pre-paint inline script so
    there's no flash on load)
  - Rebalanced UI color proportions to match the target design ratio: removed
    coral as a large section/card fill (index.html feature band -> gold,
    group.html stat tiles -> berry/gold/blue), added a new restrained
    `--accent-blue` accent (one stat tile + a small "Runs" count badge), and
    gave dark mode its own tuned accent values (muted workhorse gold,
    brighter pop coral, lightened berry) instead of reusing light-mode hexes
    unchanged
  - Verified all of the above against the real code and real data (diagnostic
    scripts run through the actual live path) and in a real browser
    (Playwright screenshots of the light/dark landing and dashboard pages)

## 2026-09-24 00:25:55
- **Message:** Fix recommendation personalization bugs, add theme toggle, rebalance UI colors
- **Author:** Krishiv Vijayakumar
- **Files changed:**
  - BUILD_LOG.md
  - backend/.env.example
  - backend/groups.py
  - backend/paths.py
  - backend/skills_impl/favorites.py
  - backend/skills_impl/geocoding.py
  - backend/skills_impl/google_oauth.py
  - backend/skills_impl/places.py
  - backend/static/app.js
  - backend/static/style.css
  - backend/templates/base.html
  - backend/templates/group.html
  - backend/templates/index.html

## Commit: Log previous commit and merge latest work into main

- Date: 2026-09-24
- Time spent: ~5 minutes (checking how the app is run/deployed, committing
  the pending build-log entry, pushing, and opening/merging the PR to main)
- Rough tokens used: ~40,000-60,000 (rough estimate from conversation length
  and tool-call volume; Claude Code doesn't expose an exact counter)
- What shipped:
  - Committed the auto-generated build-log entry for the previous commit
  - Opened and merged a PR from `assesment-2-krishiv` into `main` so `main`
    has the personalization fixes, theme toggle and UI color rebalance

## 2026-09-24 21:53:54
- **Message:** Log previous commit and merge prep in BUILD_LOG.md
- **Author:** Krishiv Vijayakumar
- **Files changed:**
  - BUILD_LOG.md

## Commit: Align theme toggle with nav buttons and keep theme across pages

- Date: 2026-09-24
- Time spent: ~15 minutes (21:53-22:08, reproducing in a local Playwright
  browser test, fixing, and re-verifying)
- Rough tokens used: ~80,000-120,000 (rough estimate from conversation
  length and tool-call volume; Claude Code doesn't expose an exact counter)
- What shipped:
  - Theme toggle now sits in the same box + label layout as the
    Dashboard/Favorites/Prefs icons (with a "Theme" label), so it lines up
    with them; scoped the per-icon background colors to the nav list so the
    toggle keeps its berry fill; lined the landing-page tagline up with it
  - Theme choice is now also saved in a `theme` cookie that base.html reads
    server-side to render `data-theme` on `<html>`, so the mode picked on
    the sign-up screen carries into the group pages even where
    localStorage is unavailable; existing localStorage choices migrate to
    the cookie automatically
  - Re-apply the saved theme on `pageshow` so pages reached with
    back/forward don't show a stale mode
  - Verified in headless Chromium: dark chosen on sign-up stays dark after
    creating a group (server-rendered), all four header boxes share the
    same top/size, no horizontal overflow at 375px

## 2026-09-24 22:08:48
- **Message:** Align theme toggle with nav buttons and keep theme across pages
- **Author:** Krishiv Vijayakumar
- **Files changed:**
  - BUILD_LOG.md
  - backend/static/app.js
  - backend/static/style.css
  - backend/templates/base.html

## Commit: Personality pass - voice, oversized type, asymmetry, hover details, loading states

- Date: 2026-09-25
- Time spent: ~50 minutes of hands-on work (2026-09-24 23:40 to 2026-09-25
  00:29, from scratch-script timestamps), done in five stages with approval
  of each before moving on
- Rough tokens used: ~300,000-600,000 (rough estimate from conversation
  length, tool-call volume and the many verification screenshots; Claude
  Code doesn't expose an exact counter)
- What shipped:
  - Microcopy: every template plus the dashboard status lines, agent errors
    and 404s in main.py rewritten in a cheeky-friend voice (approved list;
    "crew" changed to "gang" per review); response pages now say "in / out /
    a maybe" instead of the raw verdict value
  - Oversized type, used only three times: "HANG / OUT" in the home hero,
    a giant member count on the dashboard (replacing the matching stat
    tile), and a thick SVG check on the response/vote confirmation pages
  - Asymmetry on one 24px unit (`--offset`), desktop only: sign-up card
    hangs 24px into the gold band, staggered feature row, off-centre circle
    diagram with its status line dropped 24px, second stat tile dropped
    24px, hanging headings on favorites/likes
  - Hover/cursor: 1deg card tilt + lift (not on cards containing forms),
    -2deg button tilt, header icon wiggle, dot cursor over the circle
    diagram, bouncy "Name - status" tags on circle nodes; all motion off
    under prefers-reduced-motion and on touch devices
  - Loading: "Make it happen" and reply "Send" switch to a busy label and a
    status strip cycling on-brand lines every 2.5s; guards against double
    submits and resets on back/forward
  - Verified with headless Chromium: all pages render (light/dark, 1280px
    and 375px, no horizontal overflow), measured the 24px overlap, hover
    states, tooltip text, reduced-motion behaviour, and that each form
    submits exactly once while showing the loading lines

## 2026-09-25 00:30:11
- **Message:** Add personality pass: new voice, oversized type, asymmetric layout, hover details, loading states
- **Author:** Krishiv Vijayakumar
- **Files changed:**
  - BUILD_LOG.md
  - backend/main.py
  - backend/static/app.js
  - backend/static/style.css
  - backend/templates/_circle.html
  - backend/templates/favorites.html
  - backend/templates/group.html
  - backend/templates/index.html
  - backend/templates/join.html
  - backend/templates/preferences.html
  - backend/templates/respond.html
  - backend/templates/vote.html

## Commit: Put member count in an equal 3-tile stat row, share member form fields

- Date: 2026-09-25
- Time spent: ~15 minutes (measuring the reported alignment issues across
  8 viewport widths and on the live site, fixing, re-verifying)
- Rough tokens used: ~60,000-100,000 (rough estimate from conversation
  length and tool-call volume; Claude Code doesn't expose an exact counter)
- What shipped:
  - Dashboard: moved the oversized "N in the gang" count back into the
    stat row as a normal tile (same border/shadow/fill), removed the
    `.dash-head`/`.mega-*` styles, and dropped the 24px stagger on the
    second tile so the row is flat
  - `.stat-row` now uses a fixed `repeat(3, 1fr)` grid from 640px up (one
    column below) instead of `auto-fit`, so tiles are always equal width
    and can't wrap into an uneven 2 + 1
  - New `templates/_member_fields.html` macro holds the name/email,
    location and interests/dislikes fields; index.html and join.html both
    use it (with a name prefix) instead of duplicating the markup
  - Checked, no change needed: field pairs were already a 1fr 1fr grid and
    measured equal everywhere; HANG/OUT share one text-shadow rule
  - Verified in headless Chromium: create-group and join still save every
    field; tiles equal width and top at 1440-640px, stacked below; no
    horizontal overflow

