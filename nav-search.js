/* ============================================================
   Blueprint Hockey — Shared Nav Search
   Loads player index once, powers the search dropdown in nav.
   Include this on every page after shared.css/the nav HTML.
   ============================================================ */

let BP_PLAYER_INDEX = [];

const bpLogoUrl = (team) => {
  // Some logos render with better edge detail using the light variant
  // against our backgrounds (thin outlines get lost in the dark variant)
  const lightVariant = new Set(['TOR']);
  const variant = lightVariant.has(team) ? 'light' : 'dark';
  return `https://assets.nhle.com/logos/nhl/svg/${team}_${variant}.svg`;
};
const bpHeadshotUrl = (playerId) => `data/headshots/${playerId}.png`;

async function bpLoadPlayerIndex() {
  try {
    const res = await fetch('data/master_season.csv');
    const text = await res.text();
    const rows = bpParseCSV(text);
    const maxSeason = Math.max(...rows.map(r => Number(r.season)));
    BP_PLAYER_INDEX = rows
      .filter(r => Number(r.season) === maxSeason)
      .map(r => ({
        playerId: r.playerId,
        name: r.display_name || r.name,
        fullName: r.name,
        team: r.team,
        position: r.position,
        pos_group: r.pos_group,
        WAR: Number(r.WAR) || 0,
      }));
  } catch (e) {
    // Fallback sample data for preview without local files
    BP_PLAYER_INDEX = [
      { playerId: '8478402', name: 'McDavid',    fullName: 'Connor McDavid',    team: 'EDM', position: 'C', pos_group: 'F', WAR: 4.02 },
      { playerId: '8477492', name: 'MacKinnon',  fullName: 'Nathan MacKinnon',  team: 'COL', position: 'C', pos_group: 'F', WAR: 3.44 },
      { playerId: '8480801', name: 'Bouchard',   fullName: 'Evan Bouchard',     team: 'EDM', position: 'D', pos_group: 'D', WAR: 3.02 },
      { playerId: '8479318', name: 'Suzuki',     fullName: 'Nick Suzuki',       team: 'MTL', position: 'C', pos_group: 'F', WAR: 0.88 },
      { playerId: '8484801', name: 'Celebrini',  fullName: 'Macklin Celebrini', team: 'SJS', position: 'C', pos_group: 'F', WAR: 0.51 },
      { playerId: '8480800', name: 'Hughes',     fullName: 'Quinn Hughes',      team: 'MIN', position: 'D', pos_group: 'D', WAR: 2.41 },
    ];
  }
}

function bpParseCSV(text) {
  const lines = text.trim().split('\n');
  const headers = lines[0].split(',').map(h => h.trim().replace(/^"|"$/g, ''));
  return lines.slice(1).map(line => {
    const vals = []; let cur = ''; let inQ = false;
    for (const c of line) {
      if (c === '"') { inQ = !inQ; }
      else if (c === ',' && !inQ) { vals.push(cur.trim()); cur = ''; }
      else cur += c;
    }
    vals.push(cur.trim());
    const obj = {};
    headers.forEach((h, i) => { obj[h] = (vals[i] || '').replace(/^"|"$/g, ''); });
    return obj;
  });
}

function bpInitNavSearch() {
  // Hamburger toggle — wired here (not a separate function) so every
  // existing page that already calls bpInitNavSearch() after injecting
  // nav.html picks this up automatically, with no per-page changes needed.
  // Placed before the search-element guard below so it still runs even
  // if search elements are ever missing for some reason.
  const navToggle = document.getElementById('bp-nav-toggle');
  const navLinks = document.querySelector('.bp-nav-links');
  // Guard against bpInitNavSearch() being called more than once on the same
  // page (confirmed directly happening — getEventListeners() showed two
  // click listeners stacked on the same button, which silently canceled
  // each other out: one click fired both, opening then immediately
  // re-closing the menu, so nothing visibly happened). This flag makes the
  // wiring safe to run repeatedly instead of chasing down every possible
  // reason bpInitNavSearch() might get called twice.
  if (navToggle && navLinks && !navToggle.dataset.wired) {
    navToggle.dataset.wired = 'true';
    navToggle.addEventListener('click', function() {
      const isOpen = navLinks.classList.toggle('open');
      navToggle.classList.toggle('open', isOpen);
      navToggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
    });
    navLinks.querySelectorAll('a').forEach(function(a) {
      a.addEventListener('click', function() {
        navLinks.classList.remove('open');
        navToggle.classList.remove('open');
        navToggle.setAttribute('aria-expanded', 'false');
      });
    });
  }

  const input = document.getElementById('bp-nav-search-input');
  const results = document.getElementById('bp-nav-search-results');
  if (!input || !results) return;

  function renderResults(query) {
    if (!query) { results.classList.remove('open'); results.innerHTML = ''; return; }
    const q = query.toLowerCase();
    const matches = BP_PLAYER_INDEX
      .filter(p => p.fullName.toLowerCase().includes(q) || p.team.toLowerCase().includes(q))
      .sort((a, b) => b.WAR - a.WAR)
      .slice(0, 8);

    if (!matches.length) {
      results.innerHTML = '<div class="bp-search-empty">No players found</div>';
      results.classList.add('open');
      return;
    }

    results.innerHTML = matches.map(p => `
      <div class="bp-search-result" onclick="window.location.href='player.html?id=${p.playerId}'">
        <img class="bp-search-headshot" src="${bpHeadshotUrl(p.playerId)}" alt=""
             onerror="this.style.display='none'">
        <div class="bp-search-info">
          <div class="bp-search-name">${p.fullName}</div>
          <div class="bp-search-meta">
            <img class="bp-search-logo" src="${bpLogoUrl(p.team)}" alt="${p.team}" onerror="this.style.display='none'">
            ${p.team} &middot; ${p.position}
          </div>
        </div>
        <div class="bp-search-war">${p.WAR >= 0 ? '+' : ''}${p.WAR.toFixed(2)}</div>
      </div>
    `).join('');
    results.classList.add('open');
  }

  input.addEventListener('input', e => renderResults(e.target.value));
  input.addEventListener('focus', e => { if (e.target.value) renderResults(e.target.value); });
  document.addEventListener('click', e => {
    if (!e.target.closest('.bp-search-wrap')) {
      results.classList.remove('open');
    }
  });
}

document.addEventListener('DOMContentLoaded', async () => {
  await bpLoadPlayerIndex();
  bpInitNavSearch();
});
