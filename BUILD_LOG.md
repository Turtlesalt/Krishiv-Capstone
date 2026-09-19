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

