IDEA:
I have a large friend group, and often we struggle to spend time together because no one can see everyone's free time at once, shared interests/tasks go untracked, and coordinating a meetup means manual back-and-forth across many people.
This agent coordinates multiple people's calendars, assignments, interests, weather, and past activities to plan hangouts and group tasks based on their location. This makes it easier for everyone in the group to spend time together that they would otherwise waste.

It also notices when two or more people are working toward the same deadline — same assignment, same exam, same crunch period — and proposes co-working or study sessions for them, since that overlap is wasted in exactly the same way an unplanned free evening is.

An agent that negotiates group plans autonomously, rather than just computing overlaps and firing off a message.

The agent runs as a web app, not a chatbot. Users sign up, create or join "groups" (their friend group, via an invite link), connect their Google Calendar once via OAuth, and receive all hangout proposals, task/deadline matches, and updates by email — sent to every relevant member of the group, with one-click accept/decline/tentative links, no login required to respond.

MVP:
Agent has tools: get_calendar_freebusy(person) [Google Calendar API], get_weather(location, date), get_past_plans(), get_academic_items(person) [Google Calendar–derived], send_message(person, text) [email, to the recipient's registered address]
Trigger: weekly cron or a "plan something" command, per group
Agent runs its own loop, choosing the sequence itself:
Gather calendar/weather/history/academic-deadline data
Propose a plan (time, activity, subgroup) — or a co-working session if two people share a deadline within ~48 hours
Send it by email to every invited member of the group (with accept/decline/tentative links), wait for replies
Re-evaluate based on who accepted/declined
Re-propose (smaller subgroup, different time) or explicitly report it couldn't find a fit
No hardcoded "if no reply in X hours, do Y" — the agent decides how to react to partial responses
Web app: users, groups (create/join via invite link), one shared profile per person (constraints/interests/calendar) reused across all their groups
Test group: 5–10 friends, calendars connected via Google Calendar API, delivery via email to each group member (magic-link responses)
Interest input stays simple (a short list or a form field) — full fuzzy-interest parsing comes later
Academic-item input stays calendar-derived only for MVP — no portal/LMS integration yet

FINAL GOALS
Agent handles fuzzy, soft constraints ("free most evenings unless it's raining or I've had a long day") rather than just hard free/busy blocks
Full negotiation loop per person: declines trigger a re-check of that person's constraints and a revised proposal, not just a logged "no"
Judgment calls on competing group preferences (some want gym, some want food, no formula decides — agent weighs group history, fairness, recency)
Self-aware limits: agent recognizes when it can't resolve a plan and escalates to the group (by email) instead of forcing a bad one
Academic overlap grows beyond calendar titles into opt-in college portal/LMS integration (courses, assignments, exam timetables), subject-level matching, and session sequencing before exams — read-only, opt-in per person, deadlines never shared beyond "you both have something due"
Layered on top once the negotiation core works: subgroup clustering by shared interests, location suggestions via Maps/Places, complementary-skill matching for study sessions, and a lightweight DB tracking past plans so it doesn't repeat the same activity/group combo too often

USE OF AGENT
I am aiming for a high level of AI involvement because the core value of the project depends on the agent making decisions rather than simply executing fixed rules.

The AI agent will:
- Interpret group preferences and constraints
- Decide which information it needs to gather
- Negotiate between conflicting preferences
- Detect shared deadlines/assignments and decide whether they warrant a co-working proposal
- Re-evaluate plans based on people's responses
- Decide when to propose an alternative or escalate the decision to the group

The non-AI components will handle:
- Google Calendar API access (OAuth, per-user connection)
- Weather API access
- Email delivery to group recipients (proposals, magic-link responses, digests) via a transactional email service
- Group creation/invite/membership logic (the web app layer)
- Data storage (plans, responses, academic items, history)
- Authentication (Google OAuth, doubling as calendar consent)
12