// SyncCircle client-side interactions.
//
// Vote/accept/decline-style actions in this app are plain form submits
// (the reply form, favorite delete). Before the browser navigates away we
// play a brief ripple on the button so the click feels confirmed, then
// submit for real.
// Light/dark toggle. base.html already applies any saved choice before
// first paint (inline head script) so there's no flash - this just wires
// up the click and keeps localStorage in sync.
function currentTheme() {
  const saved = document.documentElement.dataset.theme;
  if (saved === "light" || saved === "dark") return saved;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  try {
    localStorage.setItem("theme", theme);
  } catch (e) {}
}

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
