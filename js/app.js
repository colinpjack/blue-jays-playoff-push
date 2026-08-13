const $ = (id) => document.getElementById(id);

function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function fmtDate(iso, withTime = false) {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  const opts = withTime
    ? { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZone: "America/Toronto" }
    : { weekday: "short", month: "short", day: "numeric", timeZone: "America/Toronto" };
  return new Intl.DateTimeFormat("en-CA", opts).format(date);
}

function relativeTime(iso) {
  const date = new Date(iso);
  const delta = Date.now() - date.getTime();
  const mins = Math.max(0, Math.round(delta / 60000));
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return fmtDate(iso, true);
}

function record(team) {
  return `${team.wins}-${team.losses}`;
}

function streakClass(code) {
  if (!code) return "";
  if (String(code).startsWith("W")) return "hot";
  if (String(code).startsWith("L")) return "cold";
  return "";
}

function teamCell(team) {
  return `<div class="team-cell">
    <img src="${esc(team.logo)}" alt="" />
    <span>${esc(team.abbr || team.teamName)}</span>
  </div>`;
}

function nextGameLabel(team) {
  const game = (team.nextGames || [])[0];
  if (!game) return "—";
  const opp = game.opponent;
  const prefix = game.isHome ? "vs" : "@";
  return `${prefix} ${opp?.abbr || "TBD"}`;
}

function gbDisplay(value) {
  if (value === "-" || value == null || value === "") return "—";
  if (String(value).startsWith("+")) return `${value.replace("+", "")} up`;
  return String(value);
}

function renderTicker(data) {
  const jays = data.jays;
  const next = (data.schedule || [])[0];
  const nextText = next
    ? `NEXT ${next.isHome ? "vs" : "@"} ${next.opponent?.abbr || ""} ${fmtDate(next.gameDate || next.date, true)}`
    : "";
  const parts = [
    `TORONTO BLUE JAYS ${record(jays)}`,
    `WC #${jays.wildCardRank} · ${jays.wildCardGamesBack} GB`,
    `L10 ${jays.lastTen} · ${jays.streak}`,
    `RUN DIFF ${jays.runDifferential > 0 ? "+" : ""}${jays.runDifferential}`,
    nextText,
    data.narrative.headline,
    "THE PUSH IS ON",
    "UPDATED HOURLY",
  ].filter(Boolean);
  const line = parts.join("   •   ") + "   •   ";
  $("tickerTrack").textContent = line + line;
}

function renderHero(data) {
  const jays = data.jays;
  $("statusKicker").textContent = data.narrative.status === "in" ? "Holding a wild-card spot" : "American League wild-card chase";
  $("headline").textContent = data.narrative.headline;
  $("blurb").textContent = data.narrative.blurb;
  $("gbGiant").textContent = jays.wildCardGamesBack === "-" ? "0" : jays.wildCardGamesBack;
  $("recordLine").textContent = `${jays.abbr} ${record(jays)} · ${jays.pct} · AL East #${jays.divisionRank || "—"}`;
  const heat = jays.momentum ?? 0;
  $("heatValue").textContent = `${heat}`;
  $("heatFill").style.width = `${heat}%`;
  $("heroChips").innerHTML = [
    ["Streak", jays.streak],
    ["Last 10", jays.lastTen],
    ["Home", jays.home],
    ["Away", jays.away],
    ["1-run", jays.oneRun],
    ["Left / Right", `${jays.vsLeft} / ${jays.vsRight}`],
  ].map(([label, value]) => `<div class="chip"><span>${esc(label)}</span><strong>${esc(value)}</strong></div>`).join("");
  $("updatePill").textContent = `Updated ${relativeTime(data.generatedAt)}`;
  $("seasonPill").textContent = `${data.season} AL wild card`;
}

function renderKpis(data) {
  $("kpis").innerHTML = (data.kpis || []).map((kpi) => `
    <article class="kpi">
      <div class="label">${esc(kpi.label)}</div>
      <div class="value">${esc(kpi.value)}</div>
      <div class="hint">${esc(kpi.hint)}</div>
    </article>
  `).join("");
}

function renderWildCard(data) {
  const body = document.querySelector("#wildCardTable tbody");
  body.innerHTML = (data.wildCard || []).map((team) => {
    const isJays = team.id === 141;
    const inSpot = (team.wildCardRank || 99) <= 3;
    const classes = [
      inSpot ? "row-in" : "",
      isJays ? "row-jays" : "",
      team.wildCardRank === 3 ? "row-cut" : "",
    ].filter(Boolean).join(" ");
    const cut = team.wildCardRank === 3 ? `<div class="cut-note">Last ticket</div>` : "";
    return `<tr class="${classes}">
      <td>${esc(team.wildCardRank)}${cut}</td>
      <td>${teamCell(team)}${isJays ? " ★" : ""}</td>
      <td>${esc(record(team))}</td>
      <td>${esc(team.pct)}</td>
      <td>${esc(gbDisplay(team.wildCardGamesBack))}</td>
      <td>${esc(team.lastTen)}</td>
      <td class="${streakClass(team.streak)}">${esc(team.streak)}</td>
      <td>${team.runDifferential > 0 ? "+" : ""}${esc(team.runDifferential)}</td>
      <td>${esc(team.wildCardEliminationNumber || "—")}</td>
      <td>${esc(nextGameLabel(team))}</td>
    </tr>`;
  }).join("");
}

function renderEast(data) {
  const body = document.querySelector("#eastTable tbody");
  body.innerHTML = (data.alEast || []).map((team) => `
    <tr class="${team.id === 141 ? "row-jays" : ""}">
      <td>${esc(team.divisionRank)}</td>
      <td>${teamCell(team)}</td>
      <td>${esc(record(team))}</td>
      <td>${esc(team.gamesBack === "-" ? "—" : team.gamesBack)}</td>
      <td>${esc(team.lastTen)}</td>
      <td>${esc(team.home)}</td>
      <td>${esc(team.away)}</td>
    </tr>
  `).join("");
}

function renderDivLeaders(data) {
  $("divLeaders").innerHTML = (data.divisionLeaders || []).map((team) => `
    <article class="div-card">
      <img src="${esc(team.logo)}" alt="" />
      <div>
        <strong>${esc(team.name)}</strong>
        <div class="meta">${esc((team.divisionName || "").replace("American League ", "AL "))} · ${esc(record(team))} · ${esc(team.pct)}</div>
      </div>
    </article>
  `).join("");
}

function metricMax(rows, getter) {
  return Math.max(...rows.map(getter), 0.0001);
}

function renderCompare(data) {
  const race = data.race || [];
  const blocks = [
    { title: "OPS", get: (t) => parseFloat(t.hitting?.ops || 0), format: (t) => t.hitting?.ops || "—" },
    { title: "Staff ERA", get: (t) => 6 - parseFloat(t.pitching?.era || 6), format: (t) => t.pitching?.era || "—" },
    { title: "Run differential", get: (t) => Math.max(0, (t.runDifferential || 0) + 80), format: (t) => `${t.runDifferential > 0 ? "+" : ""}${t.runDifferential}` },
    { title: "Last 10 wins", get: (t) => t.lastTenWins || 0, format: (t) => t.lastTen || "—" },
  ];
  $("compare").innerHTML = blocks.map((block) => {
    const max = metricMax(race, block.get);
    const rows = [...race].sort((a, b) => block.get(b) - block.get(a)).map((team) => {
      const pct = Math.max(8, Math.round((block.get(team) / max) * 100));
      return `<div class="compare-row">
        <div class="who"><img src="${esc(team.logo)}" alt="" />${esc(team.abbr)}</div>
        <div class="bar ${team.id === 141 ? "jays" : ""}"><span style="width:${pct}%"></span></div>
        <b>${esc(block.format(team))}</b>
      </div>`;
    }).join("");
    return `<div><header>${esc(block.title)}</header>${rows}</div>`;
  }).join("");
}

function renderSchedule(data) {
  const remaining = data.remaining || {};
  const opp = (remaining.opponents || []).map((item) => `${item.games} ${item.abbr}`).join(" · ");
  $("gauntletBlurb").textContent =
    `${remaining.games || 0} games left, ${remaining.vsRace || 0} against clubs still in the wild-card mess. Remaining diet: ${opp}.`;
  $("tickets").innerHTML = (data.schedule || []).map((game) => {
    const oppTeam = game.opponent || {};
    const today = new Intl.DateTimeFormat("en-CA", { timeZone: "America/Toronto", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
    const isToday = game.date === today;
    const live = game.abstractState === "Live";
    const pitcher = game.isHome ? game.home?.probablePitcher : game.away?.probablePitcher;
    const theirs = game.isHome ? game.away?.probablePitcher : game.home?.probablePitcher;
    const score = live || game.abstractState === "Final"
      ? `${game.away?.abbr} ${game.away?.score ?? ""} @ ${game.home?.abbr} ${game.home?.score ?? ""}`
      : game.venue;
    return `<article class="ticket${isToday ? " today" : ""}">
      <div class="when">${live ? '<span class="live">LIVE</span> · ' : ""}${esc(fmtDate(game.gameDate || game.date, true))}</div>
      <h4>${game.isHome ? "vs" : "@"} ${esc(oppTeam.abbr || "TBD")}</h4>
      <div class="pitch">${esc(pitcher || "TBD")} vs ${esc(theirs || "TBD")}</div>
      <div class="venue">${esc(score || "")}</div>
    </article>`;
  }).join("");
}

function renderRooting(data) {
  const tagClass = {
    "Jays game": "jays",
    "Race game": "race",
    "Need a loss": "need",
    "Keep them down": "keep",
  };
  $("rooting").innerHTML = (data.rooting || []).map((game) => `
    <article class="root-card">
      <span class="tag ${tagClass[game.interest] || "race"}">${esc(game.interest)}</span>
      <strong>${esc(game.away?.abbr)} @ ${esc(game.home?.abbr)}</strong>
      <div class="meta">${esc(fmtDate(game.gameDate || game.date, true))}</div>
      <p>${esc(game.note)}</p>
    </article>
  `).join("");
}

function renderResults(data) {
  $("results").innerHTML = (data.recent || []).slice().reverse().map((game) => {
    const opp = game.opponent || {};
    const us = game.isHome ? game.home?.score : game.away?.score;
    const them = game.isHome ? game.away?.score : game.home?.score;
    return `<li>
      <span class="badge ${esc(game.result)}">${esc(game.result || "•")}</span>
      <span>${game.isHome ? "vs" : "@"} ${esc(opp.abbr)} · ${esc(fmtDate(game.date))}</span>
      <strong>${esc(us)}–${esc(them)}</strong>
    </li>`;
  }).join("");
}

function renderInjuries(data) {
  $("injuryMeta").innerHTML = (data.race || []).map((team) => `
    <span class="pill ghost">${esc(team.abbr)} IL ${esc(team.injuryCount ?? 0)}</span>
  `).join("");
  $("injuries").innerHTML = (data.injuries || []).map((item) => `
    <article class="injury">
      <span class="status">${esc(item.status || "IL")}</span>
      <strong>${esc(item.name)}</strong>
      <p>${esc(item.comment || "No update posted.")}</p>
    </article>
  `).join("");
}

function renderPlayers(data) {
  $("hitters").innerHTML = (data.leaders?.hitting || []).map((p) => `
    <article class="player">
      <img src="${esc(p.headshot)}" alt="" onerror="this.style.opacity='0.2'" />
      <div>
        <strong>${esc(p.name)}</strong>
        <div class="meta">${esc(p.avg)} AVG · ${esc(p.hr)} HR · ${esc(p.rbi)} RBI · ${esc(p.sb)} SB</div>
      </div>
      <div class="statline">${esc(p.ops)} OPS</div>
    </article>
  `).join("");
  $("pitchers").innerHTML = (data.leaders?.pitching || []).map((p) => `
    <article class="player">
      <img src="${esc(p.headshot)}" alt="" onerror="this.style.opacity='0.2'" />
      <div>
        <strong>${esc(p.name)}</strong>
        <div class="meta">${esc(p.role)} · ${esc(p.ip)} IP · ${esc(p.w)}-${esc(p.l)} · ${esc(p.so)} K${p.sv ? ` · ${p.sv} SV` : ""}</div>
      </div>
      <div class="statline">${esc(p.era)} ERA<br>${esc(p.whip)} WHIP</div>
    </article>
  `).join("");
}

async function boot() {
  try {
    const res = await fetch(`data.json?t=${Date.now()}`, { cache: "no-store" });
    if (!res.ok) throw new Error("Could not load data.json");
    const data = await res.json();
    renderTicker(data);
    renderHero(data);
    renderKpis(data);
    renderWildCard(data);
    renderEast(data);
    renderDivLeaders(data);
    renderCompare(data);
    renderSchedule(data);
    renderRooting(data);
    renderResults(data);
    renderInjuries(data);
    renderPlayers(data);
  } catch (err) {
    $("headline").textContent = "Dashboard needs a data refresh";
    $("blurb").textContent = "Run scripts/fetch_playoff_data.py, then push data.json to GitHub Pages.";
    console.error(err);
  }
}

boot();
