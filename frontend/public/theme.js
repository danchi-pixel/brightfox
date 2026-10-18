// Apply the saved theme before first paint (light is the default).
// Kept in a file (not inline) so the website can use a strict Content-Security-Policy.
try {
  if (localStorage.getItem("uc-theme") === "dark") document.documentElement.classList.add("dark");
} catch (e) {
  /* storage unavailable */
}
