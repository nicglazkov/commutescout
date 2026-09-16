// Distance units: miles or kilometers. The default follows the device's
// locale (US, UK, Liberia and Myanmar drive in miles); a choice made in
// Settings persists on this device, and on the account once signed in
// (the watch module mirrors it to /api/watch/prefs). Classic script so
// both the map page and /watch share one copy.
window.csUnits = (() => {
  const KEY = 'cs-units';
  const MILE_KM = 1.609344;
  let current = null;
  const locale = () => {
    try { return String(navigator.language || 'en-US'); } catch (e) { return 'en-US'; }
  };
  function localeDefault() {
    const tag = locale();
    if (/-(US|GB|LR|MM)\b/i.test(tag)) return 'mi';
    if (/^en$/i.test(tag)) return 'mi';
    return 'km';
  }
  function chosen() {
    try { const v = localStorage.getItem(KEY); return (v === 'mi' || v === 'km') ? v : null; }
    catch (e) { return null; }
  }
  function get() {
    if (!current) current = chosen() || localeDefault();
    return current;
  }
  // opts.fromServer marks a value the account already holds, so the
  // listener that mirrors choices to the server does not echo it back.
  function set(v, opts) {
    if (v !== 'mi' && v !== 'km') return;
    current = v;
    try { localStorage.setItem(KEY, v); } catch (e) { /* private mode */ }
    document.dispatchEvent(new CustomEvent('cs-units', {
      detail: { units: v, fromServer: !!(opts && opts.fromServer) } }));
  }
  const label = () => (get() === 'mi' ? 'mi' : 'km');
  const fromKm = (km) => (get() === 'mi' ? km / MILE_KM : km);
  const toKm = (v) => (get() === 'mi' ? v * MILE_KM : v);
  // fmt(km) -> "12 mi" / "3.4 km"; digits pins the decimals.
  function fmt(km, digits) {
    const v = fromKm(Number(km) || 0);
    const txt = digits == null
      ? (v >= 10 ? String(Math.round(v)) : String(Math.round(v * 10) / 10))
      : v.toFixed(digits);
    return txt + ' ' + label();
  }
  return { KEY, MILE_KM, get, set, chosen, localeDefault, label, fromKm, toKm, fmt };
})();
