const $ = (id) => document.getElementById(id);

const TERMS = {
  OPS: "On-base Plus Slugging: on-base percentage plus slugging percentage. Around .700 is average; .800+ is excellent.",
  OBP: "On-base Percentage: times reaching base (hits, walks, HBP) divided by plate appearances.",
  SLG: "Slugging Percentage: total bases divided by at-bats. Extra-base hits raise this number.",
  AVG: "Batting average: hits divided by at-bats.",
  ERA: "Earned Run Average: earned runs allowed per nine innings. Lower is better.",
  WHIP: "Walks plus Hits per Inning Pitched. Lower is better. Under 1.20 is strong.",
  GB: "Games back of the last (3rd) American League wild-card spot. A plus number means the club is already in.",
  WC: "Wild card: the three extra AL playoff berths after the three division winners.",
  L10: "Record over the last 10 games.",
  PCT: "Winning percentage: wins divided by games played.",
  RBI: "Runs Batted In: runs that score as a direct result of the batter's plate appearance.",
  HR: "Home runs.",
  SB: "Stolen bases.",
  IP: "Innings pitched. One out is a third of an inning.",
  "K/9": "Strikeouts per nine innings.",
  "W-L": "Wins and losses.",
  SV: "Saves.",
  HLD: "Holds: a reliever keeps a lead without finishing the game.",
  SP: "Starting pitcher.",
  RP: "Relief pitcher.",
  PA: "Plate appearances.",
  Diff: "Season run differential: runs scored minus runs allowed.",
  Elim: "Elimination number: Jays losses plus rival wins that mathematically end Toronto's shot.",
  Pythag: "Pythagorean record: the W-L the run differential says the team 'should' have.",
  BABIP: "Batting Average on Balls In Play. Extreme numbers often regress.",
  IL: "Injured list.",
  SOS: "Strength of remaining schedule, as opponents' winning percentage.",
};

function term(code, label = code) {
  const def = TERMS[code];
  if (!def) return esc(label);
  return `<abbr class="term" tabindex="0" title="${esc(def)}" data-tip="${esc(def)}">${esc(label)}</abbr>`;
}

function trendBadge(direction, text) {
  if (!direction || direction === "flat") {
    return text ? `<span class="trend flat">${esc(text)}</span>` : "";
  }
  const arrow = direction === "up" ? "▲" : "▼";
  return `<span class="trend ${esc(direction)}">${arrow} ${esc(text || "")}</span>`;
}

function gbTrendLabel(weekAgo) {
  if (!weekAgo || weekAgo.gbDelta == null) return "—";
  const delta = weekAgo.gbDelta;
  const abs = Math.abs(delta).toFixed(1);
  if (delta === 0) return "even";
  const text = delta < 0 ? `−${abs}` : `+${abs}`;
  return trendBadge(weekAgo.direction, text);
}

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
    data.playoffOdds?.percent != null ? `PLAYOFF ODDS ${data.playoffOdds.percent}%` : "",
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
  ].map(([label, value]) => `<div class="chip"><span>${esc(label)}</span><strong>${esc(value)}</strong></div>`).join("");
  $("updatePill").textContent = `Updated ${relativeTime(data.generatedAt)}`;
  $("seasonPill").textContent = `${data.season} AL wild card`;
  const odds = data.playoffOdds || {};
  const pct = odds.percent;
  $("oddsGiant").textContent = pct == null ? "—" : `${pct}%`;
  $("oddsLine").textContent = odds.sims
    ? `${Number(odds.sims).toLocaleString()} sims · ${odds.gamesModeled || "—"} games modeled`
    : "";
  $("oddsNote").textContent = "Based on current records, last-10 form, remaining opponents, home field, and injured lists.";
  const oddsCard = document.querySelector(".hero-score.odds");
  if (oddsCard) {
    oddsCard.classList.remove("longshot", "toss-up", "live");
    if (pct == null) {
      /* keep default */
    } else if (pct < 20) {
      oddsCard.classList.add("longshot");
    } else if (pct < 40) {
      oddsCard.classList.add("toss-up");
    } else {
      oddsCard.classList.add("live");
    }
  }
}

function renderKpis(data) {
  $("kpis").innerHTML = (data.kpis || []).map((kpi) => `
    <article class="kpi">
      <div class="label">${kpi.stat ? term(kpi.stat, kpi.label) : esc(kpi.label)}</div>
      <div class="value">${esc(kpi.value)}</div>
      <div class="hint">${esc(kpi.hint)}${kpi.trend ? ` ${trendBadge(kpi.trend, "")}` : ""}</div>
    </article>
  `).join("");
}

function renderTrends(data) {
  const cards = data.trends?.cards || [];
  $("trends").innerHTML = cards.map((card) => `
    <article class="trend-card ${esc(card.direction || "flat")}">
      <div class="label">${card.stat ? term(card.stat, card.label) : esc(card.label)}</div>
      <div class="value">${esc(card.value)} ${trendBadge(card.direction, "")}</div>
      <div class="hint">${esc(card.detail)}</div>
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
      <td>${gbTrendLabel(team.weekAgo)}</td>
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
    { title: term("OPS"), get: (t) => parseFloat(t.hitting?.ops || 0), format: (t) => t.hitting?.ops || "—" },
    { title: `Staff ${term("ERA")}`, get: (t) => 6 - parseFloat(t.pitching?.era || 6), format: (t) => t.pitching?.era || "—" },
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
        return `<div><header>${block.title}</header>${rows}</div>`;
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
  $("hitters").innerHTML = (data.leaders?.hitting || []).map((p) => {
    const hot = p.trend;
    const avgMove = p.avgChange;
    const avgTip = avgMove
      ? (avgMove.lastGame === "did not bat"
        ? "Did not bat in the last game, so the season average did not move."
        : `Season average after going ${avgMove.lastGame} in the last game.`)
      : "";
    const avgArrow = avgMove && avgMove.direction && avgMove.direction !== "flat"
      ? `<span class="trend ${esc(avgMove.direction)}" title="${esc(avgTip)}" data-tip="${esc(avgTip)}">${avgMove.direction === "up" ? "▲" : "▼"}</span>`
      : "";
    return `<article class="player">
      <img src="${esc(p.headshot)}" alt="" onerror="this.style.opacity='0.2'" />
      <div>
        <strong>${esc(p.name)}</strong>
        <div class="meta">${esc(p.position || "")} · ${esc(p.avg)} ${term("AVG")}${avgArrow} · ${esc(p.hr)} ${term("HR")} · ${esc(p.rbi)} ${term("RBI")} · ${esc(p.sb)} ${term("SB")}</div>
        ${hot?.ops ? `<div class="player-trend">${trendBadge(hot.direction, `${hot.window} ${hot.ops} OPS`)}</div>` : ""}
      </div>
      <div class="statline"><span class="statline-value">${esc(p.ops)}</span><span class="statline-label">Season ${term("OPS")}</span></div>
    </article>`;
  }).join("");
  $("pitchers").innerHTML = (data.leaders?.pitching || []).map((p) => {
    const hot = p.trend;
    return `<article class="player">
      <img src="${esc(p.headshot)}" alt="" onerror="this.style.opacity='0.2'" />
      <div>
        <strong>${esc(p.name)}</strong>
        <div class="meta">${term(p.role)} · ${esc(p.ip)} ${term("IP")} · ${esc(p.w)}-${esc(p.l)} · ${esc(p.so)} K${p.sv ? ` · ${p.sv} ${term("SV")}` : ""}</div>
        ${hot?.era ? `<div class="player-trend">${trendBadge(hot.direction, `${hot.window} ${hot.era} ERA`)}</div>` : ""}
      </div>
      <div class="statline">${esc(p.era)} ${term("ERA")}<br>${esc(p.whip)} ${term("WHIP")}</div>
    </article>`;
  }).join("");
}

function bindTermTips() {
  let tip = document.getElementById("termTip");
  if (!tip) {
    tip = document.createElement("div");
    tip.id = "termTip";
    tip.className = "term-tip";
    tip.setAttribute("role", "tooltip");
    document.body.appendChild(tip);
  }

  document.querySelectorAll("abbr.term").forEach((el) => {
    if (!el.dataset.tip && el.getAttribute("title")) {
      el.dataset.tip = el.getAttribute("title");
    }
    if (el.dataset.tip && !el.getAttribute("aria-label")) {
      el.setAttribute("aria-label", `${el.textContent}: ${el.dataset.tip}`);
    }
    el.removeAttribute("title");
  });

  const place = (el) => {
    const text = el.dataset.tip;
    if (!text) return;
    tip.textContent = text;
    tip.classList.add("show");
    const pad = 12;
    const gap = 8;
    const rect = el.getBoundingClientRect();
    const tw = tip.offsetWidth;
    const th = tip.offsetHeight;
    let left = rect.left + rect.width / 2 - tw / 2;
    left = Math.max(pad, Math.min(left, window.innerWidth - tw - pad));
    let top = rect.top - th - gap;
    if (top < pad) top = Math.min(rect.bottom + gap, window.innerHeight - th - pad);
    tip.style.left = `${Math.round(left)}px`;
    tip.style.top = `${Math.round(top)}px`;
  };

  const hide = () => tip.classList.remove("show");

  document.addEventListener("pointerover", (event) => {
    const el = event.target.closest?.("abbr.term");
    if (el) place(el);
  });
  document.addEventListener("pointerout", (event) => {
    const el = event.target.closest?.("abbr.term");
    if (!el) return;
    const next = event.relatedTarget;
    if (next && el.contains(next)) return;
    hide();
  });
  document.addEventListener("focusin", (event) => {
    const el = event.target.closest?.("abbr.term");
    if (el) place(el);
  });
  document.addEventListener("focusout", hide);
  window.addEventListener("scroll", hide, true);
}

async function boot() {
  try {
    const res = await fetch(`data.json?t=${Date.now()}`, { cache: "no-store" });
    if (!res.ok) throw new Error("Could not load data.json");
    const data = await res.json();
    renderTicker(data);
    renderHero(data);
    renderKpis(data);
    renderTrends(data);
    renderWildCard(data);
    renderEast(data);
    renderDivLeaders(data);
    renderCompare(data);
    renderSchedule(data);
    renderRooting(data);
    renderResults(data);
    renderInjuries(data);
    renderPlayers(data);
    bindTermTips();
  } catch (err) {
    $("headline").textContent = "Dashboard needs a data refresh";
    $("blurb").textContent = "Run scripts/fetch_playoff_data.py, then push data.json to GitHub Pages.";
    console.error(err);
  }
}

boot();
