// Menu button for the .topbar on the static app pages (watch, trip,
// admin). At 960px and below the nav is hidden behind this button so the bar
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
// links are always in the HTML; at 960px and below they are listed in place in
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

// The theme switch in the site-style header (sitebar.css), the same one
// the site has: flips <html data-theme>, stores the choice under
// "cs-theme" (the key the site and the map read) and tells the page, so
// a page with a map can swap its base map.
(function () {
  var btn = document.querySelector(".themetoggle");
  if (!btn) return;
  var root = document.documentElement;
  function label() {
    var next = root.dataset.theme === "dark" ? "light" : "dark";
    btn.setAttribute("aria-label", "Switch to " + next + " theme");
    btn.title = "Switch to " + next + " theme";
  }
  label();
  btn.addEventListener("click", function () {
    var next = root.dataset.theme === "dark" ? "light" : "dark";
    root.dataset.theme = next;
    try { localStorage.setItem("cs-theme", next); } catch (e) { /* private mode */ }
    label();
    document.dispatchEvent(new CustomEvent("cs-theme", { detail: { theme: next } }));
  });
})();

// The account menu: hidden until the watch module fills #who (the email
// and a Sign out button), then a button with the account's initial that
// opens it. Escape and a click outside close it.
(function () {
  var acct = document.querySelector(".sitebar .acct");
  var who = document.getElementById("who");
  if (!acct || !who) return;
  var btn = acct.querySelector(".acctbtn");
  var initial = acct.querySelector(".avatar");
  function set(open) {
    acct.classList.toggle("open", open);
    btn.setAttribute("aria-expanded", open ? "true" : "false");
  }
  function sync() {
    var name = who.querySelector("span");
    var email = name ? name.textContent.trim() : "";
    acct.hidden = !email;
    if (!email) set(false);
    initial.textContent = email ? email.charAt(0).toUpperCase() : "";
    btn.setAttribute("aria-label", email ? "Account: " + email : "Account");
  }
  new MutationObserver(sync).observe(who, { childList: true, subtree: true });
  sync();
  btn.addEventListener("click", function () { set(!acct.classList.contains("open")); });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && acct.classList.contains("open")) { set(false); btn.focus(); }
  });
  document.addEventListener("pointerdown", function (e) {
    if (!acct.contains(e.target)) set(false);
  });
})();
