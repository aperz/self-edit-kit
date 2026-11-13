// Cookie consent + Meta Pixel. PROTECTED FILE — legal/compliance, not content.
//
// Mechanism: nothing third-party loads until the visitor clicks "Akceptuję".
// The choice is stored in localStorage under KEY; on later visits an earlier
// "yes" loads the pixel straight away and no banner is shown. Any element with
// [data-consent-open] (the footer link) reopens the banner so consent can be
// withdrawn — withdrawing removes the stored "yes" and reloads, so the pixel
// script from this visit is gone too.
(function () {
  var KEY = "consent-v1";
  var PIXEL_ID = "000000000000000"; // placeholder — the real ID goes in per client

  function read() {
    try { return localStorage.getItem(KEY); } catch (e) { return null; }
  }
  function write(v) {
    try { localStorage.setItem(KEY, v); } catch (e) { /* private mode: ask again next time */ }
  }

  // Standard Meta Pixel bootstrap, only ever called after consent.
  function loadPixel() {
    if (window.fbq || PIXEL_ID === "000000000000000") return;
    !function (f, b, e, v, n, t, s) {
      if (f.fbq) return; n = f.fbq = function () { n.callMethod ? n.callMethod.apply(n, arguments) : n.queue.push(arguments); };
      if (!f._fbq) f._fbq = n; n.push = n; n.loaded = !0; n.version = "2.0"; n.queue = [];
      t = b.createElement(e); t.async = !0; t.src = v; s = b.getElementsByTagName(e)[0]; s.parentNode.insertBefore(t, s);
    }(window, document, "script", "https://connect.facebook.net/en_US/fbevents.js");
    window.fbq("init", PIXEL_ID);
    window.fbq("track", "PageView");
  }

  function showBanner() {
    if (document.querySelector(".consent")) return;
    var box = document.createElement("div");
    box.className = "consent";
    box.setAttribute("role", "dialog");
    box.setAttribute("aria-label", "Zgoda na pliki cookies");
    box.innerHTML =
      '<p>Używam plików cookies (piksel Meta), żeby mierzyć skuteczność reklam. Wczytam je tylko za Twoją zgodą. ' +
      'Szczegóły w <a href="/polityka-prywatnosci.html">polityce prywatności</a>.</p>' +
      '<button class="yes" type="button">Akceptuję</button>' +
      '<button class="no" type="button">Tylko niezbędne</button>';
    box.querySelector(".yes").onclick = function () { write("yes"); box.remove(); loadPixel(); };
    box.querySelector(".no").onclick = function () {
      var hadYes = read() === "yes";
      write("no"); box.remove();
      if (hadYes) location.reload(); // drop the already-loaded pixel
    };
    document.body.appendChild(box);
  }

  document.addEventListener("click", function (ev) {
    var t = ev.target.closest && ev.target.closest("[data-consent-open]");
    if (t) { ev.preventDefault(); showBanner(); }
  });

  var choice = read();
  if (choice === "yes") loadPixel();
  else if (choice !== "no") showBanner();
})();
