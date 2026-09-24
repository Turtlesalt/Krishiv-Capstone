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

document.addEventListener("DOMContentLoaded", () => {
  const toggle = document.getElementById("theme-toggle");
  if (toggle) {
    toggle.addEventListener("click", () => {
      setTheme(currentTheme() === "dark" ? "light" : "dark");
    });
  }

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const rippleDelay = reducedMotion ? 0 : 280;

  document.querySelectorAll("form.reply-form, form.person-switch").forEach((form) => {
    const btn = form.querySelector('button[type="submit"]');
    if (!btn) return;
    form.addEventListener("submit", (event) => {
      if (btn.dataset.rippled) return;
      event.preventDefault();
      btn.dataset.rippled = "true";
      btn.classList.add("btn-ripple");
      window.setTimeout(() => form.requestSubmit ? form.requestSubmit(btn) : form.submit(), rippleDelay);
    });
  });
});
