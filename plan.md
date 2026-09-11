IDEA:
I have a large friend group, and often we struggle to spend time together because no one can see everyone's free time at once, shared interests/tasks go untracked, and coordinating a meetup means manual back-and-forth across many people. 
This agent coordinates multiple people's calendars, assignments, interests, weather, and past activities to plan hangouts and group tasks based on their location. This makes it easier for everyone in the group to spend time together that they would otherwise waste.

An agent that negotiates group plans autonomously, rather than just computing overlaps and firing off a message. 

MVP:
Agent has tools: get_calendar_freebusy(person), get_weather(location, date), get_past_plans(), send_message(person, text)
Trigger: weekly cron or a "plan something" command
Agent runs its own loop, choosing the sequence itself:
Gather calendar/weather/history data
Propose a plan (time, activity, subgroup)
Send it, wait for replies
Re-evaluate based on who accepted/declined
Re-propose (smaller subgroup, different time) or explicitly report it couldn't find a fit
No hardcoded "if no reply in X hours, do Y" — the agent decides how to react to partial responses
Test group: 5–10 friends, calendars connected via Google Calendar API, delivery via Telegram bot
Interest input stays simple (a short list or chat command) — full fuzzy-interest parsing comes later

FINAL GOALS
Agent handles fuzzy, soft constraints ("free most evenings unless it's raining or I've had a long day") rather than just hard free/busy blocks
Full negotiation loop per person: declines trigger a re-check of that person's constraints and a revised proposal, not just a logged "no"
Judgment calls on competing group preferences (some want gym, some want food, no formula decides — agent weighs group history, fairness, recency)
Self-aware limits: agent recognizes when it can't resolve a plan and escalates to the group instead of forcing a bad one
Layered on top once the negotiation core works: subgroup clustering by shared interests, location suggestions via Maps/Places, and a lightweight DB tracking past plans so it doesn't repeat the same activity/group combo too often

USE OF AGENT
AI can be used to understand peoples moods, repeating interests, completed activities, and undertanding submlinal feelings