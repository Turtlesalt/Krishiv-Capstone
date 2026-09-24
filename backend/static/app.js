// SyncCircle client-side interactions.
//
// Vote/accept/decline-style actions in this app are plain form submits
// (the reply form, favorite delete). Before the browser navigates away we
// play a brief ripple on the button so the click feels confirmed, then
// submit for real.
// Light/dark toggle. The choice is saved in a "theme" cookie, which the
// server reads to render data-theme on <html> for every page (so it
// carries over from the sign-up screen into the group pages even where
// localStorage is blocked); localStorage is kept as a fallback that the
// inline head script in base.html also reads.
function currentTheme() {
  const saved = document.documentElement.dataset.theme;
  if (saved === "light" || saved === "dark") return saved;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  document.cookie = "theme=" + theme + "; path=/; max-age=31536000; SameSite=Lax";
  try {
    localStorage.setItem("theme", theme);
  } catch (e) {}
}

// Pages shown via back/forward can come from a cache holding whatever
// theme they had when left, so re-apply the saved choice on every show.
window.addEventListener("pageshow", () => {
  const match = document.cookie.match(/(?:^|; )theme=(light|dark)/);
  if (match) document.documentElement.dataset.theme = match[1];
});

// Agent "thinking" state. Planning and replies make the server wait on the
// agent (often 10-30s+), so the submit button flips to a busy label and a
// status strip under the form cycles through on-brand lines until the page
// navigates. Guarding on form.dataset.busy also stops double submits.
const AGENT_LINES = {
  plan: [
    "Herding cats\u2026",
    "Checking who's actually free\u2026",
    "Asking the sky about the weather\u2026",
    "Finding somewhere that isn't a chain\u2026",
    "Writing the group email so you don't have to\u2026",
  ],
  work: [
    "Reading everyone\u2019s calendars\u2026",
    "Spotting shared deadlines\u2026",
    "Finding a time you\u2019re all free\u2026",
    "Sending study invites\u2026",
  ],
  reply: [
    "Passing it along\u2026",
    "Re-thinking the plan\u2026",
    "Checking this works for everyone else\u2026",
  ],
};

function startAgentLoading(form, kind) {
  const btn = form.querySelector('button[type="submit"]');
  const lines = AGENT_LINES[kind];
  form.dataset.busy = "true";
  if (btn) {
    btn.dataset.label = btn.textContent;
    btn.textContent = kind === "reply" ? "Sending\u2026" : kind === "work" ? "Checking\u2026" : "On it\u2026";
    btn.classList.add("is-busy");
    btn.setAttribute("aria-disabled", "true");
  }
  const strip = document.createElement("div");
  strip.className = "agent-loader";
  strip.setAttribute("role", "status");
  strip.setAttribute("aria-live", "polite");
  strip.innerHTML = '<span class="agent-dots" aria-hidden="true"><i></i><i></i><i></i></span><span class="agent-line"></span>';
  const line = strip.querySelector(".agent-line");
  let i = 0;
  line.textContent = lines[0];
  form.after(strip);
  form._agentTimer = window.setInterval(() => {
    i = (i + 1) % lines.length;
    line.textContent = lines[i];
    line.classList.remove("is-new");
    void line.offsetWidth;
    line.classList.add("is-new");
  }, 2500);
}

function resetAgentLoading(form) {
  window.clearInterval(form._agentTimer);
  delete form.dataset.busy;
  delete form.dataset.sent;
  const btn = form.querySelector('button[type="submit"]');
  if (btn && btn.dataset.label) {
    btn.textContent = btn.dataset.label;
    btn.classList.remove("is-busy", "btn-ripple");
    btn.removeAttribute("aria-disabled");
    delete btn.dataset.rippled;
  }
  const strip = form.nextElementSibling;
  if (strip && strip.classList.contains("agent-loader")) strip.remove();
}

// Coming back to the page via back/forward can restore it mid-"thinking";
// clear that so the form is usable again.
window.addEventListener("pageshow", (event) => {
  if (!event.persisted) return;
  document.querySelectorAll("form[data-busy]").forEach(resetAgentLoading);
});

document.addEventListener("DOMContentLoaded", () => {
  const toggle = document.getElementById("theme-toggle");
  if (toggle) {
    toggle.addEventListener("click", () => {
      setTheme(currentTheme() === "dark" ? "light" : "dark");
    });
  }

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Circle diagram name tags: hovering a person's node pops a small
  // "Name · status" tag above it. One shared element, repositioned.
  const nodes = document.querySelectorAll(".circle-node[data-name]");
  if (nodes.length) {
    const tip = document.createElement("div");
    tip.className = "node-tip";
    tip.setAttribute("aria-hidden", "true");
    document.body.appendChild(tip);
    const show = (node) => {
      tip.textContent = node.dataset.name + " \u00b7 " + node.dataset.status;
      tip.dataset.status = node.dataset.status;
      const r = node.getBoundingClientRect();
      tip.style.left = r.left + r.width / 2 + window.scrollX + "px";
      tip.style.top = r.top + window.scrollY - 8 + "px";
      tip.classList.remove("is-visible");
      void tip.offsetWidth; // restart the entrance animation
      tip.classList.add("is-visible");
    };
    const hide = () => tip.classList.remove("is-visible");
    nodes.forEach((node) => {
      node.addEventListener("mouseenter", () => show(node));
      node.addEventListener("mouseleave", hide);
    });
  }
  const rippleDelay = reducedMotion ? 0 : 280;

  document.querySelectorAll('form[action$="/plan"]').forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (form.dataset.busy) { event.preventDefault(); return; }
      startAgentLoading(form, "plan");
    });
  });

  document.querySelectorAll("form.check-work-form").forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (form.dataset.busy) { event.preventDefault(); return; }
      startAgentLoading(form, "work");
    });
  });

  document.querySelectorAll("form.reply-form").forEach((form) => {
    const btn = form.querySelector('button[type="submit"]');
    if (!btn) return;
    form.addEventListener("submit", (event) => {
      if (btn.dataset.rippled) {
        // second pass (our own requestSubmit) goes through; anything after is a double submit
        if (form.dataset.sent) { event.preventDefault(); return; }
        form.dataset.sent = "true";
        return;
      }
      event.preventDefault();
      btn.dataset.rippled = "true";
      btn.classList.add("btn-ripple");
      startAgentLoading(form, "reply");
      window.setTimeout(() => form.requestSubmit ? form.requestSubmit(btn) : form.submit(), rippleDelay);
    });
  });
});
