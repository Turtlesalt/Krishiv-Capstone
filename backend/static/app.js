// SyncCircle client-side interactions.
//
// Vote/accept/decline-style actions in this app are plain form submits
// (the reply form, favorite delete). Before the browser navigates away we
// play a brief ripple on the button so the click feels confirmed, then
// submit for real.
document.addEventListener("DOMContentLoaded", () => {
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
