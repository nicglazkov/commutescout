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

// The Developers menu in the map page's top bar (map.html), the same
// menu the site header has. Hover opens it for a mouse; the button opens
// it for touch and keyboard; Escape and a click outside close it. The
// links are always in the HTML; below 640px they are listed in place in
// the Menu sheet, so the menu button is not needed there.
(function () {
  var menu = document.querySelector(".topbar .devmenu");
  var btn = menu && menu.querySelector(".devbtn");
  if (!btn) return;
  var timer;
  function set(open) {
    menu.classList.toggle("open", open);
    btn.setAttribute("aria-expanded", open ? "true" : "false");
  }
  btn.addEventListener("click", function () { set(!menu.classList.contains("open")); });
  menu.addEventListener("pointerenter", function (e) {
    if (e.pointerType !== "mouse") return;
    clearTimeout(timer); set(true);
  });
  menu.addEventListener("pointerleave", function (e) {
    if (e.pointerType !== "mouse") return;
    timer = setTimeout(function () { set(false); }, 160);
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && menu.classList.contains("open")) { set(false); btn.focus(); }
  });
  document.addEventListener("pointerdown", function (e) {
    if (!menu.contains(e.target)) set(false);
  });
})();
