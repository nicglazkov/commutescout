// Menu button for the .topbar on the static app pages (watch, trip,
// admin). Below 640px the nav is hidden behind this button so the bar
// stays one row, matching the site's Next.js header. The CSS for both
// states lives in each page's own <style>; this only flips the class.
(function () {
  var bar = document.querySelector(".topbar");
  var btn = bar && bar.querySelector(".navmenu");
  if (!btn) return;
  btn.addEventListener("click", function () {
    var open = bar.classList.toggle("open");
    btn.setAttribute("aria-expanded", open ? "true" : "false");
    btn.setAttribute("aria-label", open ? "Close menu" : "Menu");
  });
})();
