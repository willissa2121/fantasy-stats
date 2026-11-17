const PALETTE = [
  "#d00",
  "#1d4ed8",
  "#0f766e",
  "#9333ea",
  "#c2410c",
  "#0369a1",
  "#4d7c0f",
  "#be185d",
];

const THEME_KEY = "fs-theme";

function currentTheme() {
  return document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";
}

function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  try {
    localStorage.setItem(THEME_KEY, theme);
  } catch (_) {
    /* ignore quota / private mode */
  }
  const button = document.getElementById("theme-toggle");
  if (button) {
    button.setAttribute(
      "aria-label",
      theme === "dark" ? "Switch to light mode" : "Switch to dark mode"
    );
  }
}

function bootTheme() {
  let theme = "dark";
  try {
    theme = localStorage.getItem(THEME_KEY) === "light" ? "light" : "dark";
  } catch (_) {
    /* keep default */
  }
  applyTheme(theme);
  document.getElementById("theme-toggle")?.addEventListener("click", () => {
    applyTheme(currentTheme() === "dark" ? "light" : "dark");
  });
}

bootTheme();

async function loadLeague() {
  const response = await fetch("./data/league.json");
  if (!response.ok) {
    throw new Error("Could not load league data");
  }
  return response.json();
}

function colorFor(id) {
  let hash = 0;
  for (const char of id) {
    hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
  }
  return PALETTE[hash % PALETTE.length];
}

function initials(name) {
  const parts = name.trim().split(/\s+/);
  return parts
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}

function formatPct(value) {
  return `${(value * 100).toFixed(1)}%`;
}

function formatNum(value, digits = 1) {
  return Number(value).toFixed(digits);
}

function yearsLabel(player) {
  if (player.first_season === player.last_season) {
    return String(player.first_season);
  }
  return `${player.first_season}–${player.last_season}`;
}

function playerHref(id) {
  return `./player.html?id=${encodeURIComponent(id)}`;
}

function cardHtml(player) {
  return `
    <a class="card" href="${playerHref(player.id)}">
      <div class="avatar" style="background:${colorFor(player.id)}">${initials(player.name)}</div>
      <div>
        <h2>${player.name}</h2>
        <div class="meta">${player.latest_team}</div>
        <div class="tiny">${yearsLabel(player)} · ${player.career.gp} GP</div>
        <div class="record">${player.career.record} · ${formatPct(player.career.win_pct)}</div>
      </div>
    </a>
  `;
}

function sectionHtml(title, subtitle, players, extraClass = "") {
  if (!players.length) {
    return "";
  }
  return `
    <section class="roster ${extraClass}">
      <div class="roster-head">
        <h2>${title}</h2>
        <p>${subtitle}</p>
      </div>
      <div class="grid">
        ${players.map(cardHtml).join("")}
      </div>
    </section>
  `;
}

function renderRosters(active, legacy) {
  const root = document.getElementById("rosters");
  if (!active.length && !legacy.length) {
    root.innerHTML = `<p class="empty">No players match that search.</p>`;
    return;
  }
  root.innerHTML = [
    sectionHtml(
      "Active players",
      `${active.length} in the current season`,
      active
    ),
    sectionHtml(
      "Legacy players",
      "No longer in the league",
      legacy,
      "legacy"
    ),
  ].join("");
}

async function bootIndex() {
  try {
    const league = await loadLeague();
    const copy = document.getElementById("hero-copy");
    const first = league.league.seasons[0];
    const current = league.league.seasons[league.league.seasons.length - 1];
    copy.textContent = `${league.players.length} managers · ${first}–${current}`;
    const search = document.getElementById("search");
    const draw = () => {
      const query = search.value.trim().toLowerCase();
      const filtered = league.players.filter((player) => {
        const haystack = [
          player.name,
          player.latest_team,
          ...(player.aliases || []),
          ...(player.seasons || []).map((season) => season.team),
        ]
          .join(" ")
          .toLowerCase();
        return haystack.includes(query);
      });
      const active = filtered.filter((player) => player.last_season === current);
      const legacy = filtered.filter((player) => player.last_season !== current);
      renderRosters(active, legacy);
    };
    search.addEventListener("input", draw);
    draw();
  } catch (error) {
    document.getElementById("rosters").innerHTML =
      `<p class="empty">${error.message}</p>`;
  }
}

function seasonRows(player) {
  const rows = player.seasons
    .map(
      (season) => `
      <tr>
        <td>${season.season}</td>
        <td>${season.team}</td>
        <td class="num">${season.gp}</td>
        <td class="num">${season.wins}</td>
        <td class="num">${season.losses}</td>
        <td class="num">${formatPct(season.win_pct)}</td>
        <td class="num">${formatNum(season.pf, 1)}</td>
        <td class="num">${formatNum(season.pa, 1)}</td>
        <td class="num">${formatNum(season.ppg)}</td>
        <td class="num">${formatNum(season.diff, 1)}</td>
        <td class="num">${formatNum(season.high)}</td>
        <td class="num">${formatNum(season.low)}</td>
      </tr>
    `
    )
    .join("");
  const career = player.career;
  return (
    rows +
    `
    <tr class="career-row">
      <td>Career</td>
      <td>${player.seasons.length} seasons</td>
      <td class="num">${career.gp}</td>
      <td class="num">${career.wins}</td>
      <td class="num">${career.losses}</td>
      <td class="num">${formatPct(career.win_pct)}</td>
      <td class="num">${formatNum(career.pf, 1)}</td>
      <td class="num">${formatNum(career.pa, 1)}</td>
      <td class="num">${formatNum(career.ppg)}</td>
      <td class="num">${formatNum(career.diff, 1)}</td>
      <td class="num">${formatNum(career.high)}</td>
      <td class="num">${formatNum(career.low)}</td>
    </tr>
  `
  );
}

function renderPlayer(player) {
  const root = document.getElementById("player-root");
  document.title = `${player.name} · League History`;
  root.innerHTML = `
    <section class="player-hero">
      <div class="wrap">
        <a class="back" href="./">← All players</a>
        <div class="player-hero-grid">
        <div class="player-avatar" style="background:${colorFor(player.id)}">${initials(player.name)}</div>
        <div class="player-id">
          <h1>${player.name}</h1>
          <div class="team">${player.latest_team} · ${yearsLabel(player)}</div>
          <div class="fact-row">
            <div class="fact"><span>Seasons</span><b>${player.seasons.length}</b></div>
            <div class="fact"><span>Games</span><b>${player.career.gp}</b></div>
            <div class="fact"><span>Debut</span><b>${player.first_season}</b></div>
            <div class="fact"><span>Record</span><b>${player.career.record}</b></div>
          </div>
        </div>
        <aside class="statbox">
          <h2>Career Stats</h2>
          <div class="statbox-grid">
            <div>
              <span>Win%</span>
              <strong>${formatPct(player.career.win_pct)}</strong>
            </div>
            <div>
              <span>PF/G</span>
              <strong>${formatNum(player.career.ppg)}</strong>
            </div>
            <div>
              <span>Diff</span>
              <strong>${formatNum(player.career.diff, 1)}</strong>
            </div>
            <div>
              <span>High</span>
              <strong>${formatNum(player.career.high, 1)}</strong>
            </div>
          </div>
        </aside>
        </div>
      </div>
    </section>
    <section class="wrap panel">
      <div class="panel-head">
        <h2>Stats</h2>
        <div class="tiny">Regular season scoring · ${yearsLabel(player)}</div>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Season</th>
              <th>Team</th>
              <th class="num">GP</th>
              <th class="num">W</th>
              <th class="num">L</th>
              <th class="num">Win%</th>
              <th class="num">PF</th>
              <th class="num">PA</th>
              <th class="num">Avg</th>
              <th class="num">Diff</th>
              <th class="num">High</th>
              <th class="num">Low</th>
            </tr>
          </thead>
          <tbody>
            ${seasonRows(player)}
          </tbody>
        </table>
      </div>
    </section>
  `;
}

const STAT_SECTIONS = [
  { id: "points", title: "Points", subtitle: "Scoring output and weekly explosions" },
  { id: "records", title: "Records", subtitle: "Wins, losses, and winning percentage" },
  { id: "margins", title: "Margins", subtitle: "Blowouts, squeakers, and differentials" },
  { id: "streaks", title: "Streaks", subtitle: "Runs of form" },
  { id: "moments", title: "Moments", subtitle: "The weird ones" },
];

function whoHtml(entry) {
  return `
    <a class="leader-who" href="${playerHref(entry.player_id)}">
      <div class="avatar" style="background:${colorFor(entry.player_id)}">${initials(entry.player_name)}</div>
      <span>${entry.player_name}</span>
    </a>
  `;
}

function chevronHtml() {
  return `
    <span class="leader-toggle" aria-hidden="true">
      <svg viewBox="0 0 12 8"><path d="M1 1.5L6 6.5 11 1.5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>
    </span>
  `;
}

function followRow(entry, rank) {
  return `
    <div class="leader-follow">
      <div class="follow-copy">
        <span class="rank">${rank}</span>
        <span class="follow-detail">${entry.detail || ""}</span>
      </div>
      ${whoHtml(entry)}
      <div class="leader-stat">${entry.value}</div>
      <span class="leader-toggle is-empty" aria-hidden="true"></span>
    </div>
  `;
}

function leaderRow(award) {
  const entries = award.entries || [];
  const top = entries[0];
  if (!top) {
    return "";
  }
  const rest = entries.slice(1);
  const moreLabel = `Show next ${rest.length} ${award.blurb.toLowerCase()}`;
  return `
    <article class="leader-group">
      <div class="leader">
        ${
          rest.length
            ? `<button type="button" class="leader-expand" data-expand aria-expanded="false" aria-label="${moreLabel}"></button>`
            : ""
        }
        <div class="leader-copy">
          <span class="kicker">${award.blurb}</span>
          <strong>${award.title}</strong>
          <span class="detail">${top.detail || ""}</span>
        </div>
        ${whoHtml(top)}
        <div class="leader-stat">${top.value}</div>
        ${rest.length ? chevronHtml() : `<span class="leader-toggle is-empty" aria-hidden="true"></span>`}
      </div>
      ${
        rest.length
          ? `<div class="leader-more">
              ${rest.map((entry, index) => followRow(entry, index + 2)).join("")}
            </div>`
          : ""
      }
    </article>
  `;
}

function renderAwards(awards) {
  const root = document.getElementById("stats-root");
  if (!awards || !awards.length) {
    root.innerHTML = `<p class="empty">No stats available for this scope.</p>`;
    return;
  }
  const grouped = Object.fromEntries(STAT_SECTIONS.map((section) => [section.id, []]));
  for (const award of awards) {
    const group = grouped[award.group] ? award.group : "moments";
    grouped[group].push(award);
  }
  root.innerHTML = `
    <div class="stat-page">
      ${STAT_SECTIONS.filter((section) => grouped[section.id].length)
        .map(
          (section) => `
        <section class="stat-block">
          <h2>${section.title}</h2>
          <p>${section.subtitle}</p>
          <div class="leaderboard">
            ${grouped[section.id].map(leaderRow).join("")}
          </div>
        </section>
      `
        )
        .join("")}
    </div>
  `;
}

function bindAwardExpand(root) {
  root.addEventListener("click", (event) => {
    const button = event.target.closest("[data-expand]");
    if (!button || !root.contains(button)) {
      return;
    }
    const group = button.closest(".leader-group");
    if (!group) {
      return;
    }
    const open = group.classList.toggle("is-open");
    button.setAttribute("aria-expanded", String(open));
    const rest = group.querySelectorAll(".leader-follow").length;
    button.setAttribute(
      "aria-label",
      open ? "Hide extra results" : `Show next ${rest} results`
    );
  });
}

async function bootStats() {
  const root = document.getElementById("stats-root");
  try {
    const league = await loadLeague();
    const copy = document.getElementById("hero-copy");
    const select = document.getElementById("scope");
    const current = league.stats.current_season;
    const years = [...league.league.seasons].sort((a, b) => b - a);
    select.innerHTML = [
      ...years.map((year) => `<option value="${year}">${year}</option>`),
      `<option value="all_time">All time</option>`,
    ].join("");
    select.value = String(current);
    const draw = () => {
      const allTime = select.value === "all_time";
      if (allTime) {
        copy.textContent = `Every season from ${years[years.length - 1]}–${current}`;
        renderAwards(league.stats.all_time);
        return;
      }
      const year = select.value;
      const week = (league.stats.through_weeks || {})[year] || league.stats.through_week;
      copy.textContent = `${year} regular season · through week ${week}`;
      renderAwards((league.stats.by_season || {})[year] || []);
    };
    bindAwardExpand(root);
    select.addEventListener("change", draw);
    draw();
  } catch (error) {
    root.innerHTML = `<p class="empty">${error.message}</p>`;
  }
}

async function bootPlayer() {
  const root = document.getElementById("player-root");
  const id = new URLSearchParams(window.location.search).get("id");
  try {
    const league = await loadLeague();
    const player = league.players.find((item) => item.id === id);
    if (!player) {
      root.innerHTML = `<p class="empty">Player not found. <a href="./">Back to roster</a></p>`;
      return;
    }
    renderPlayer(player);
  } catch (error) {
    root.innerHTML = `<p class="empty">${error.message}</p>`;
  }
}
