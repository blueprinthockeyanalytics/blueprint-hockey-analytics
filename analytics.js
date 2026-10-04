// analytics.js -- visitor counts (Cloudflare Web Analytics: free, no cookies).
// Paste the token from Cloudflare (dash.cloudflare.com -> Analytics & Logs ->
// Web Analytics -> your site -> "Manage site" -> JS snippet, the "token" value)
// between the quotes below. While it's empty, nothing is loaded.
(function () {
  var CF_TOKEN = "5005f5a387d64be8952468887ee456ab";
  if (!CF_TOKEN) return;
  if (window.top !== window.self) return;          // compare page's embedded cards: don't double count
  if (/^(localhost|127\.)/.test(location.hostname)) return;
  var s = document.createElement("script");
  s.defer = true;
  s.src = "https://static.cloudflareinsights.com/beacon.min.js";
  s.setAttribute("data-cf-beacon", JSON.stringify({ token: CF_TOKEN }));
  document.head.appendChild(s);
})();
