#!/usr/bin/env python3
"""Fetch Blue Jays playoff-race data and write data.json for GitHub Pages."""

from __future__ import annotations

import hashlib
import json
import random
import ssl
import subprocess
import time
import urllib.request
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Toronto")
JAYS_ID = 141
AL_ID = 103
NL_ID = 104
USER_AGENT = "BlueJaysPlayoffDash/1.0 (+github-pages hourly refresh)"
ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = ROOT / "data.json"

DIVISION_NAMES = {
    200: "American League West",
    201: "American League East",
    202: "American League Central",
    203: "National League East",
    204: "National League Central",
    205: "National League West",
}

TEAM_COLORS = {
    141: "#134A8E",  # Blue Jays
    147: "#0C2340",  # Yankees
    111: "#BD3039",  # Red Sox
    139: "#092C5C",  # Rays
    110: "#DF4601",  # Orioles
    140: "#003278",  # Rangers
    142: "#002B5C",  # Twins
    116: "#0C2340",  # Tigers
    114: "#00385D",  # Guardians
    136: "#0C2C56",  # Mariners
    145: "#27251F",  # White Sox
    117: "#002D62",  # Astros
    118: "#004687",  # Royals
    133: "#003831",  # Athletics
}


def toronto_now() -> datetime:
    return datetime.now(TZ)


def season_year(now: datetime) -> int:
    return now.year - 1 if now.month < 3 else now.year


def fetch_json(url: str, retries: int = 3) -> dict:
    last_err: Exception | None = None
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            ctx = ssl.create_default_context()
            with urllib.request.urlopen(req, timeout=45, context=ctx) as resp:
                return json.load(resp)
        except Exception as err:
            last_err = err
            time.sleep(0.6 * (attempt + 1))
    # Local macOS Python often lacks certs; curl usually still works.
    try:
        completed = subprocess.run(
            ["curl", "-sS", "-A", USER_AGENT, url],
            check=True,
            capture_output=True,
            text=True,
            timeout=45,
        )
        return json.loads(completed.stdout)
    except Exception as curl_err:
        raise RuntimeError(f"Failed to fetch {url}: {last_err} / {curl_err}") from curl_err


def split_map(record: dict) -> dict[str, dict]:
    splits = (record.get("records") or {}).get("splitRecords") or []
    return {item.get("type"): item for item in splits if item.get("type")}


def parse_gb(value) -> float | None:
    if value in (None, "-", "", "—"):
        return 0.0 if value == "-" else None
    try:
        text = str(value).replace("+", "")
        return float(text)
    except (TypeError, ValueError):
        return None


def pythagorean(runs_scored: int, runs_allowed: int, games: int) -> tuple[int, int, float]:
    if runs_scored <= 0 and runs_allowed <= 0:
        return 0, games, 0.5
    exponent = 1.83
    rs = max(runs_scored, 0) ** exponent
    ra = max(runs_allowed, 0) ** exponent
    pct = rs / (rs + ra) if (rs + ra) else 0.5
    wins = round(pct * games)
    return wins, games - wins, round(pct, 3)


def compact_team(team: dict) -> dict:
    return {
        "id": team.get("id"),
        "name": team.get("name"),
        "teamName": team.get("teamName") or team.get("clubName") or team.get("name"),
        "location": team.get("locationName") or team.get("shortName"),
        "abbr": team.get("abbreviation") or team.get("fileCode", "").upper(),
        "fileCode": team.get("fileCode"),
        "logo": f"https://www.mlbstatic.com/team-logos/{team.get('id')}.svg",
        "color": TEAM_COLORS.get(team.get("id"), "#1D4ED8"),
    }


def summarize_record(record: dict, division_name: str | None = None) -> dict:
    team = compact_team(record.get("team") or {})
    splits = split_map(record)
    last_ten = splits.get("lastTen") or {}
    home = splits.get("home") or {}
    away = splits.get("away") or {}
    one_run = splits.get("oneRun") or {}
    extra = splits.get("extraInning") or {}
    day = splits.get("day") or {}
    night = splits.get("night") or {}
    vs_left = splits.get("left") or {}
    vs_right = splits.get("right") or {}
    expected = (record.get("records") or {}).get("expectedRecords") or []
    xwl = next((item for item in expected if item.get("type") == "xWinLoss"), None)
    rs = int(record.get("runsScored") or 0)
    ra = int(record.get("runsAllowed") or 0)
    gp = int(record.get("gamesPlayed") or 0)
    pyth_w, pyth_l, pyth_pct = pythagorean(rs, ra, gp)
    wcgb_raw = record.get("wildCardGamesBack")
    streak = record.get("streak") or {}
    return {
        **team,
        "wins": int(record.get("wins") or 0),
        "losses": int(record.get("losses") or 0),
        "pct": record.get("winningPercentage") or (record.get("leagueRecord") or {}).get("pct"),
        "gamesPlayed": gp,
        "gamesRemaining": max(0, 162 - gp),
        "divisionRank": int(record.get("divisionRank") or 0) or None,
        "leagueRank": int(record.get("leagueRank") or 0) or None,
        "wildCardRank": int(record.get("wildCardRank") or 0) or None,
        "gamesBack": record.get("gamesBack"),
        "wildCardGamesBack": wcgb_raw,
        "wildCardGamesBackNum": parse_gb(wcgb_raw),
        "divisionName": division_name,
        "streak": streak.get("streakCode"),
        "streakType": streak.get("streakType"),
        "streakNumber": streak.get("streakNumber"),
        "lastTen": f"{last_ten.get('wins', 0)}-{last_ten.get('losses', 0)}" if last_ten else None,
        "lastTenWins": int(last_ten.get("wins") or 0) if last_ten else 0,
        "lastTenLosses": int(last_ten.get("losses") or 0) if last_ten else 0,
        "home": f"{home.get('wins', 0)}-{home.get('losses', 0)}" if home else None,
        "away": f"{away.get('wins', 0)}-{away.get('losses', 0)}" if away else None,
        "oneRun": f"{one_run.get('wins', 0)}-{one_run.get('losses', 0)}" if one_run else None,
        "extraInning": f"{extra.get('wins', 0)}-{extra.get('losses', 0)}" if extra else None,
        "day": f"{day.get('wins', 0)}-{day.get('losses', 0)}" if day else None,
        "night": f"{night.get('wins', 0)}-{night.get('losses', 0)}" if night else None,
        "vsLeft": f"{vs_left.get('wins', 0)}-{vs_left.get('losses', 0)}" if vs_left else None,
        "vsRight": f"{vs_right.get('wins', 0)}-{vs_right.get('losses', 0)}" if vs_right else None,
        "runsScored": rs,
        "runsAllowed": ra,
        "runDifferential": int(record.get("runDifferential") or (rs - ra)),
        "pythagWins": pyth_w,
        "pythagLosses": pyth_l,
        "pythagPct": pyth_pct,
        "expectedRecord": f"{xwl.get('wins')}-{xwl.get('losses')}" if xwl else None,
        "eliminationNumber": record.get("eliminationNumber"),
        "wildCardEliminationNumber": record.get("wildCardEliminationNumber"),
        "clinched": bool(record.get("clinched")),
        "divisionLeader": bool(record.get("divisionLeader") or record.get("divisionChamp")),
    }


def pick_stat(stat: dict, keys: list[str]) -> dict:
    out = {}
    for key in keys:
        if key in stat:
            out[key] = stat[key]
    return out


HITTING_KEYS = [
    "avg", "obp", "slg", "ops", "runs", "hits", "homeRuns", "rbi",
    "stolenBases", "strikeOuts", "baseOnBalls", "babip",
]
PITCHING_KEYS = [
    "era", "whip", "wins", "losses", "saves", "strikeOuts", "baseOnBalls",
    "inningsPitched", "strikeoutsPer9Inn", "walksPer9Inn", "homeRunsPer9",
    "holds", "blownSaves", "winPercentage",
]


def game_payload(game: dict, focus_id: int | None = None) -> dict:
    status = game.get("status") or {}
    home = (game.get("teams") or {}).get("home") or {}
    away = (game.get("teams") or {}).get("away") or {}
    home_team = compact_team(home.get("team") or {})
    away_team = compact_team(away.get("team") or {})
    is_home = home_team.get("id") == focus_id if focus_id else None
    opponent = away_team if is_home else home_team if is_home is False else None
    home_score = home.get("score")
    away_score = away.get("score")
    result = None
    if focus_id and status.get("abstractGameState") == "Final" and home_score is not None:
        jays_score = home_score if is_home else away_score
        opp_score = away_score if is_home else home_score
        if jays_score > opp_score:
            result = "W"
        elif jays_score < opp_score:
            result = "L"
        else:
            result = "T"
    linescore = game.get("linescore") or {}
    probable_home = (home.get("probablePitcher") or {}).get("fullName")
    probable_away = (away.get("probablePitcher") or {}).get("fullName")
    return {
        "gamePk": game.get("gamePk"),
        "date": game.get("officialDate"),
        "gameDate": game.get("gameDate"),
        "dayNight": game.get("dayNight"),
        "venue": (game.get("venue") or {}).get("name"),
        "status": status.get("detailedState") or status.get("abstractGameState"),
        "abstractState": status.get("abstractGameState"),
        "inning": linescore.get("currentInning"),
        "inningState": linescore.get("inningState"),
        "home": {**home_team, "score": home_score, "probablePitcher": probable_home, "record": (home.get("leagueRecord") or {})},
        "away": {**away_team, "score": away_score, "probablePitcher": probable_away, "record": (away.get("leagueRecord") or {})},
        "isHome": is_home,
        "opponent": opponent,
        "result": result,
        "seriesGameNumber": game.get("seriesGameNumber"),
        "gamesInSeries": game.get("gamesInSeries"),
    }


def momentum_score(team: dict) -> int:
    gb = team.get("wildCardGamesBackNum")
    gb_term = 40 if gb is None else max(0, 40 - int(gb * 10))
    l10 = team.get("lastTenWins", 0) * 6
    streak_n = team.get("streakNumber") or 0
    streak = streak_n * 4 if team.get("streakType") == "wins" else -streak_n * 3
    rd = max(-20, min(20, (team.get("runDifferential") or 0) // 4))
    rank = team.get("wildCardRank") or 9
    rank_term = max(0, 24 - rank * 3)
    return max(0, min(100, gb_term + l10 + streak + rd + rank_term))


HOME_ADVANTAGE = 0.038
PLAYOFF_SIMS = 5000


def parse_pct(value, default: float = 0.5) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def injury_drag(team: dict, detailed_injuries: list[dict] | None = None) -> float:
    if detailed_injuries:
        drag = 0.0
        for inj in detailed_injuries:
            status = (inj.get("status") or "").lower()
            if "10" in status:
                drag += 0.007
            elif "15" in status:
                drag += 0.009
            elif "60" in status:
                drag += 0.001
            else:
                drag += 0.004
        return min(0.04, drag)
    return min(0.035, 0.0028 * int(team.get("injuryCount") or 0))


def team_talent(team: dict, detailed_injuries: list[dict] | None = None) -> float:
    actual = parse_pct(team.get("pct"))
    pyth = team.get("pythagPct")
    pyth = float(pyth) if pyth is not None else actual
    l10w = int(team.get("lastTenWins") or 0)
    l10l = int(team.get("lastTenLosses") or 0)
    l10n = l10w + l10l
    recent = (l10w / l10n) if l10n else actual
    base = 0.45 * pyth + 0.30 * actual + 0.25 * recent
    base -= injury_drag(team, detailed_injuries)
    return max(0.33, min(0.67, base))


def log5(p_win: float, p_lose: float) -> float:
    a = max(0.05, min(0.95, p_win))
    b = max(0.05, min(0.95, p_lose))
    num = a * (1 - b)
    den = num + b * (1 - a)
    return num / den if den else 0.5


def remaining_al_matchups(all_games: list[dict], al_ids: set[int]) -> list[tuple[int, int]]:
    games = []
    seen = set()
    for game in all_games:
        if (game.get("status") or {}).get("abstractGameState") == "Final":
            continue
        pk = game.get("gamePk")
        if not pk or pk in seen:
            continue
        home = ((game.get("teams") or {}).get("home") or {}).get("team") or {}
        away = ((game.get("teams") or {}).get("away") or {}).get("team") or {}
        hid, aid = home.get("id"), away.get("id")
        if not hid or not aid:
            continue
        hid, aid = int(hid), int(aid)
        if hid not in al_ids and aid not in al_ids:
            continue
        seen.add(pk)
        games.append((hid, aid))
    return games


def simulate_playoff_odds(
    all_al: dict[int, dict],
    all_records: dict[int, dict],
    all_games: list[dict],
    jays_injuries: list[dict],
    n: int = PLAYOFF_SIMS,
) -> dict:
    al_ids = set(all_al.keys())
    matchups = remaining_al_matchups(all_games, al_ids)
    talent: dict[int, float] = {}
    for tid, team in all_records.items():
        talent[tid] = team_talent(team)
    for tid, team in all_al.items():
        extra = jays_injuries if tid == JAYS_ID else None
        talent[tid] = team_talent(team, extra)

    divisions: dict[str, list[int]] = defaultdict(list)
    for tid, team in all_al.items():
        divisions[team.get("divisionName") or "Unknown"].append(tid)

    start_wins = {tid: int(team.get("wins") or 0) for tid, team in all_al.items()}
    run_diff = {tid: int(team.get("runDifferential") or 0) for tid, team in all_al.items()}

    seed_src = json.dumps(
        [(tid, all_al[tid].get("wins"), all_al[tid].get("losses")) for tid in sorted(all_al)]
        + [len(matchups), len(jays_injuries)],
        separators=(",", ":"),
    )
    rng = random.Random(int(hashlib.md5(seed_src.encode()).hexdigest()[:16], 16))

    made = 0
    for _ in range(n):
        wins = dict(start_wins)
        for hid, aid in matchups:
            p_home = log5(talent.get(hid, 0.5) + HOME_ADVANTAGE, talent.get(aid, 0.5))
            if rng.random() < p_home:
                if hid in wins:
                    wins[hid] += 1
            elif aid in wins:
                wins[aid] += 1
        winners = set()
        for ids in divisions.values():
            if ids:
                winners.add(sorted(ids, key=lambda tid: (wins[tid], run_diff[tid]), reverse=True)[0])
        rest = sorted(
            (tid for tid in all_al if tid not in winners),
            key=lambda tid: (wins[tid], run_diff[tid]),
            reverse=True,
        )
        if JAYS_ID in winners or JAYS_ID in rest[:3]:
            made += 1

    percent = round(100.0 * made / n, 1)
    jays_team = all_al.get(JAYS_ID) or {}
    return {
        "percent": percent,
        "sims": n,
        "made": made,
        "gamesModeled": len(matchups),
        "talent": round(talent.get(JAYS_ID, 0), 3),
        "method": (
            "Monte Carlo of remaining American League games. Each game uses log5 win odds from "
            "Pythagorean record, season record, last-10 form, home-field advantage, and injured-list drag."
        ),
        "note": (
            f"{percent}% of {n:,} sims have Toronto as a division winner or one of the three AL wild cards. "
            f"Models {len(matchups)} remaining games involving AL clubs."
        ),
        "gb": jays_team.get("wildCardGamesBack"),
        "gamesLeft": jays_team.get("gamesRemaining"),
    }


def wild_card_magic(jays: dict, wild_card: list[dict]) -> dict | None:
    rank = jays.get("wildCardRank") or 99
    cut = next((team for team in wild_card if team.get("wildCardRank") == 3), None)
    fourth = next((team for team in wild_card if team.get("wildCardRank") == 4), None)
    if rank <= 3 and fourth:
        value = max(0, 163 - int(jays.get("wins") or 0) - int(fourth.get("losses") or 0))
        return {
            "kind": "clinch",
            "value": value,
            "toTie": None,
            "vs": fourth.get("abbr"),
            "vsName": fourth.get("name"),
            "hint": f"Jays wins + {fourth.get('abbr')} losses to clinch a wild-card berth",
            "detail": f"Classic magic number vs {fourth.get('abbr')}, the first club currently on the outside.",
        }
    if not cut:
        return None
    to_tie = max(0, int(cut.get("wins") or 0) - int(jays.get("wins") or 0) + int(jays.get("losses") or 0) - int(cut.get("losses") or 0))
    to_pass = to_tie + 1
    return {
        "kind": "get-in",
        "value": to_pass,
        "toTie": to_tie,
        "vs": cut.get("abbr"),
        "vsName": cut.get("name"),
        "hint": f"Jays wins + {cut.get('abbr')} losses to pass the last wild-card spot",
        "detail": f"{to_tie} to tie {cut.get('abbr')}, {to_pass} to go ahead of today's cut line.",
    }


def narrative_for(jays: dict) -> dict:
    rank = jays.get("wildCardRank") or 99
    gb = jays.get("wildCardGamesBackNum")
    streak = jays.get("streak") or ""
    if rank <= 3:
        status = "in"
        headline = "In the dance"
        blurb = "Toronto currently holds an American League wild-card position. Every remaining game is about staying there."
    elif gb is not None and gb <= 2:
        status = "chasing"
        headline = "Right on the cut line"
        blurb = "The Jays are within shouting distance of the last wild-card spot. This is a real October hunt."
    elif gb is not None and gb <= 5:
        status = "hunting"
        headline = "Still in the hunt"
        blurb = "The math is alive. Toronto needs a heater — and a few losses from the clubs they are chasing."
    else:
        status = "longshot"
        headline = "Long shot, not lights out"
        blurb = "The gap is real, but the remaining schedule still has chances to make noise."
    if streak.startswith("W") and status in {"chasing", "hunting"}:
        blurb += f" Momentum check: they are riding a {streak} streak."
    return {"status": status, "headline": headline, "blurb": blurb}


def match_espn_team(name: str, abbr: str, espn_teams: list[dict]) -> dict | None:
    name_l = (name or "").lower()
    abbr_l = (abbr or "").lower()
    for team in espn_teams:
        display = (team.get("displayName") or "").lower()
        if name_l and (name_l in display or display in name_l):
            return team
        if abbr_l and abbr_l in display.split():
            return team
    aliases = {
        "blue jays": "toronto",
        "yankees": "yankees",
        "red sox": "red sox",
        "rangers": "rangers",
        "twins": "twins",
        "tigers": "tigers",
        "guardians": "guardians",
        "orioles": "orioles",
        "mariners": "mariners",
        "rays": "rays",
    }
    needle = None
    for key, val in aliases.items():
        if key in name_l:
            needle = val
            break
    if needle:
        for team in espn_teams:
            if needle in (team.get("displayName") or "").lower():
                return team
    return None


def injury_items(espn_team: dict | None, fallback: list[dict]) -> list[dict]:
    items = []
    if espn_team:
        for inj in espn_team.get("injuries") or []:
            athlete = inj.get("athlete") or {}
            items.append(
                {
                    "name": athlete.get("displayName"),
                    "status": inj.get("status"),
                    "comment": inj.get("shortComment") or inj.get("longComment"),
                    "date": inj.get("date"),
                    "position": None,
                }
            )
        return items
    return fallback


def splits_by_player(payload: dict) -> dict[int, dict]:
    out: dict[int, dict] = {}
    for split in (payload.get("stats") or [{}])[0].get("splits") or []:
        pid = (split.get("player") or {}).get("id")
        if pid:
            out[int(pid)] = split
    return out


def first_split_stat(payload: dict) -> dict:
    splits = (payload.get("stats") or [{}])[0].get("splits") or []
    return (splits[0].get("stat") or {}) if splits else {}


def headshot_url(player_id: int | None) -> str:
    return (
        "https://img.mlbstatic.com/mlb-photos/image/upload/"
        "d_people:generic:headshot:67:current.png/w_180,q_auto:best/"
        f"v1/people/{player_id}/headshot/67/current"
    )


def relative_to_cut(wcgb_raw) -> float | None:
    if wcgb_raw in (None, ""):
        return None
    text = str(wcgb_raw)
    if text == "-":
        return 0.0
    if text.startswith("+"):
        return -float(text[1:] or 0)
    try:
        return float(text)
    except ValueError:
        return None


def trend_dir(delta: float | None, *, invert: bool = False, deadzone: float = 0.0) -> str:
    if delta is None:
        return "flat"
    value = -delta if invert else delta
    if abs(value) <= deadzone:
        return "flat"
    return "up" if value > 0 else "down"


def parse_ip(value) -> float:
    text = str(value or "0")
    if "." in text:
        whole, frac = text.split(".", 1)
        try:
            return int(whole) + int(frac) / 3
        except ValueError:
            return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def week_ago_map(standings: dict) -> dict[int, dict]:
    out: dict[int, dict] = {}
    for block in standings.get("records") or []:
        if block.get("standingsType") and block.get("standingsType") != "wildCard":
            continue
        for rec in block.get("teamRecords") or []:
            team = rec.get("team") or {}
            tid = team.get("id")
            if not tid:
                continue
            out[int(tid)] = {
                "wildCardRank": int(rec.get("wildCardRank") or 0) or None,
                "wildCardGamesBack": rec.get("wildCardGamesBack"),
                "rel": relative_to_cut(rec.get("wildCardGamesBack")),
                "wins": int(rec.get("wins") or 0),
                "losses": int(rec.get("losses") or 0),
            }
    return out


def apply_week_trends(teams: list[dict], prior: dict[int, dict]) -> None:
    for team in teams:
        prev = prior.get(team["id"])
        if not prev:
            continue
        now_rel = relative_to_cut(team.get("wildCardGamesBack"))
        then_rel = prev.get("rel")
        gb_delta = None
        if now_rel is not None and then_rel is not None:
            gb_delta = round(now_rel - then_rel, 1)
        rank_now = team.get("wildCardRank")
        rank_then = prev.get("wildCardRank")
        rank_delta = None
        if rank_now and rank_then:
            rank_delta = rank_now - rank_then
        team["weekAgo"] = {
            "wildCardRank": rank_then,
            "wildCardGamesBack": prev.get("wildCardGamesBack"),
            "wins": prev.get("wins"),
            "losses": prev.get("losses"),
            "gbDelta": gb_delta,
            "rankDelta": rank_delta,
            "direction": trend_dir(gb_delta, invert=True, deadzone=0.05),
        }


def active_roster_maps(roster_payload: dict) -> tuple[dict[int, dict], set[int], set[int]]:
    by_id: dict[int, dict] = {}
    hitters: set[int] = set()
    pitchers: set[int] = set()
    for entry in roster_payload.get("roster") or []:
        person = entry.get("person") or {}
        pid = person.get("id")
        if not pid:
            continue
        pid = int(pid)
        pos = (entry.get("position") or {}).get("abbreviation") or "DH"
        item = {
            "id": pid,
            "name": person.get("fullName"),
            "position": pos,
            "status": (entry.get("status") or {}).get("description"),
            "jersey": entry.get("jerseyNumber"),
        }
        by_id[pid] = item
        if pos == "P":
            pitchers.add(pid)
        else:
            hitters.add(pid)
    return by_id, hitters, pitchers


def last_game_batting(game_pk: int | None) -> dict[int, dict]:
    if not game_pk:
        return {}
    box = fetch_json(f"https://statsapi.mlb.com/api/v1/game/{game_pk}/boxscore")
    out: dict[int, dict] = {}
    for side in ("home", "away"):
        team = (box.get("teams") or {}).get(side) or {}
        if (team.get("team") or {}).get("id") != JAYS_ID:
            continue
        for player in (team.get("players") or {}).values():
            person = player.get("person") or {}
            pid = person.get("id")
            stat = (player.get("stats") or {}).get("batting") or {}
            if not pid or not stat:
                continue
            out[int(pid)] = {
                "atBats": int(stat.get("atBats") or 0),
                "hits": int(stat.get("hits") or 0),
                "summary": stat.get("summary"),
            }
    return out


def mlb_avg(hits: int, at_bats: int) -> str | None:
    if at_bats <= 0:
        return None
    value = hits / at_bats
    text = f"{value:.3f}"
    return text[1:] if text.startswith("0") else text


def build_hitters(
    season_payload: dict,
    l10_payload: dict,
    hitter_ids: set[int],
    roster: dict[int, dict],
    last_game: dict[int, dict] | None = None,
) -> list[dict]:
    season = splits_by_player(season_payload)
    last10 = splits_by_player(l10_payload)
    last_game = last_game or {}
    rows = []
    for pid in hitter_ids:
        split = season.get(pid)
        stat = (split or {}).get("stat") or {}
        pa = int(stat.get("plateAppearances") or 0)
        l10_stat = (last10.get(pid) or {}).get("stat") or {}
        l10_pa = int(l10_stat.get("plateAppearances") or 0)
        if pa < 15 and l10_pa < 10:
            continue
        info = roster[pid]
        season_ops = float(stat.get("ops") or 0) if stat.get("ops") else None
        hot_ops = float(l10_stat.get("ops") or 0) if l10_stat.get("ops") else None
        delta = round(hot_ops - season_ops, 3) if season_ops is not None and hot_ops is not None else None
        season_h = int(stat.get("hits") or 0)
        season_ab = int(stat.get("atBats") or 0)
        game = last_game.get(pid)
        avg_change = None
        if game and season_ab > 0:
            game_ab = int(game.get("atBats") or 0)
            game_h = int(game.get("hits") or 0)
            prev_ab = season_ab - game_ab
            prev_h = season_h - game_h
            current = mlb_avg(season_h, season_ab)
            previous = mlb_avg(prev_h, prev_ab) if prev_ab > 0 else None
            direction = "flat"
            if previous and current:
                if current > previous:
                    direction = "up"
                elif current < previous:
                    direction = "down"
            elif game_ab == 0:
                direction = "flat"
            avg_change = {
                "direction": direction,
                "from": previous,
                "to": current,
                "lastGame": f"{game_h}-for-{game_ab}" if game_ab else "did not bat",
            }
        rows.append(
            {
                "id": pid,
                "name": info["name"],
                "position": info["position"],
                "headshot": headshot_url(pid),
                "avg": stat.get("avg"),
                "obp": stat.get("obp"),
                "slg": stat.get("slg"),
                "ops": stat.get("ops"),
                "hr": stat.get("homeRuns"),
                "rbi": stat.get("rbi"),
                "sb": stat.get("stolenBases"),
                "hits": season_h,
                "ab": season_ab,
                "pa": pa,
                "games": stat.get("gamesPlayed"),
                "avgChange": avg_change,
                "trend": {
                    "window": "L10",
                    "avg": l10_stat.get("avg"),
                    "ops": l10_stat.get("ops"),
                    "hr": l10_stat.get("homeRuns"),
                    "pa": l10_pa or None,
                    "delta": delta,
                    "direction": trend_dir(delta, deadzone=0.02),
                } if l10_stat else None,
            }
        )
    rows.sort(key=lambda r: (-(r["pa"] or 0), -float(r.get("ops") or 0)))
    return rows


def build_pitchers(season_payload: dict, l14_payload: dict, pitcher_ids: set[int], roster: dict[int, dict]) -> list[dict]:
    season = splits_by_player(season_payload)
    last14 = splits_by_player(l14_payload)
    rows = []
    for pid in pitcher_ids:
        split = season.get(pid)
        stat = (split or {}).get("stat") or {}
        ip_val = parse_ip(stat.get("inningsPitched"))
        l14_stat = (last14.get(pid) or {}).get("stat") or {}
        l14_ip = parse_ip(l14_stat.get("inningsPitched"))
        if ip_val < 3 and l14_ip < 2:
            continue
        info = roster[pid]
        gs = int(stat.get("gamesStarted") or 0)
        games = int(stat.get("gamesPitched") or stat.get("gamesPlayed") or 0)
        season_era = float(stat.get("era") or 0) if stat.get("era") not in (None, "") else None
        hot_era = float(l14_stat.get("era") or 0) if l14_stat.get("era") not in (None, "") else None
        delta = round(hot_era - season_era, 2) if season_era is not None and hot_era is not None else None
        role = "SP" if gs >= 5 and (games == 0 or gs / games >= 0.45) else "RP"
        rows.append(
            {
                "id": pid,
                "name": info["name"],
                "position": info["position"],
                "headshot": headshot_url(pid),
                "era": stat.get("era"),
                "whip": stat.get("whip"),
                "ip": stat.get("inningsPitched"),
                "w": stat.get("wins"),
                "l": stat.get("losses"),
                "so": stat.get("strikeOuts"),
                "sv": stat.get("saves"),
                "hld": stat.get("holds"),
                "gs": gs,
                "g": games,
                "k9": stat.get("strikeoutsPer9Inn"),
                "role": role,
                "trend": {
                    "window": "L14",
                    "era": l14_stat.get("era"),
                    "whip": l14_stat.get("whip"),
                    "ip": l14_stat.get("inningsPitched"),
                    "so": l14_stat.get("strikeOuts"),
                    "delta": delta,
                    "direction": trend_dir(delta, invert=True, deadzone=0.25),
                } if l14_stat else None,
            }
        )
    rows.sort(key=lambda r: (0 if r["role"] == "SP" else 1, -parse_ip(r.get("ip"))))
    return rows


def main() -> None:
    now = toronto_now()
    season = season_year(now)
    today = now.date()
    start_recent = today - timedelta(days=14)
    end_upcoming = date(season, 10, 5)

    standings = fetch_json(
        "https://statsapi.mlb.com/api/v1/standings"
        f"?leagueId={AL_ID},{NL_ID}&season={season}"
        "&standingsTypes=wildCard,regularSeason&hydrate=team"
    )
    hitting = fetch_json(
        f"https://statsapi.mlb.com/api/v1/teams/stats?group=hitting&season={season}&sportIds=1&stats=season"
    )
    pitching = fetch_json(
        f"https://statsapi.mlb.com/api/v1/teams/stats?group=pitching&season={season}&sportIds=1&stats=season"
    )
    schedule = fetch_json(
        "https://statsapi.mlb.com/api/v1/schedule?sportId=1"
        f"&startDate={start_recent.isoformat()}&endDate={end_upcoming.isoformat()}"
        "&hydrate=probablePitcher,linescore,team"
    )
    jays_hitters = fetch_json(
        "https://statsapi.mlb.com/api/v1/stats?stats=season&group=hitting"
        f"&season={season}&teamId={JAYS_ID}&sportIds=1&limit=50&playerPool=all"
    )
    jays_pitchers = fetch_json(
        "https://statsapi.mlb.com/api/v1/stats?stats=season&group=pitching"
        f"&season={season}&teamId={JAYS_ID}&sportIds=1&limit=50&playerPool=all"
    )
    jays_hitters_l10 = fetch_json(
        "https://statsapi.mlb.com/api/v1/stats?stats=lastXGames&group=hitting"
        f"&season={season}&teamId={JAYS_ID}&sportIds=1&limit=50&playerPool=all"
    )
    range_start = (today - timedelta(days=14)).isoformat()
    range_end = today.isoformat()
    jays_pitchers_l14 = fetch_json(
        "https://statsapi.mlb.com/api/v1/stats?stats=byDateRange&group=pitching"
        f"&season={season}&teamId={JAYS_ID}&sportIds=1&limit=50&playerPool=all"
        f"&startDate={range_start}&endDate={range_end}"
    )
    team_hit_l14 = fetch_json(
        f"https://statsapi.mlb.com/api/v1/teams/{JAYS_ID}/stats?season={season}"
        f"&group=hitting&stats=byDateRange&startDate={range_start}&endDate={range_end}"
    )
    team_pitch_l14 = fetch_json(
        f"https://statsapi.mlb.com/api/v1/teams/{JAYS_ID}/stats?season={season}"
        f"&group=pitching&stats=byDateRange&startDate={range_start}&endDate={range_end}"
    )
    week_ago = (today - timedelta(days=7)).isoformat()
    week_ago_standings = fetch_json(
        "https://statsapi.mlb.com/api/v1/standings"
        f"?leagueId={AL_ID}&season={season}&standingsTypes=wildCard&date={week_ago}&hydrate=team"
    )
    jays_active = fetch_json(
        f"https://statsapi.mlb.com/api/v1/teams/{JAYS_ID}/roster?rosterType=active&season={season}"
    )
    jays_40man = fetch_json(
        f"https://statsapi.mlb.com/api/v1/teams/{JAYS_ID}/roster?rosterType=40Man&season={season}"
    )
    espn = fetch_json("https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/injuries")

    hitting_by_id = {
        (split.get("team") or {}).get("id"): split.get("stat") or {}
        for split in (hitting.get("stats") or [{}])[0].get("splits") or []
    }
    pitching_by_id = {
        (split.get("team") or {}).get("id"): split.get("stat") or {}
        for split in (pitching.get("stats") or [{}])[0].get("splits") or []
    }

    al_east: list[dict] = []
    al_west_leaders = []
    division_leaders = []
    wild_card: list[dict] = []
    all_al: dict[int, dict] = {}
    all_records: dict[int, dict] = {}

    for block in standings.get("records") or []:
        division_id = (block.get("division") or {}).get("id")
        division = DIVISION_NAMES.get(division_id) or (block.get("division") or {}).get("name")
        standings_type = block.get("standingsType")
        league_id = (block.get("league") or {}).get("id")
        for rec in block.get("teamRecords") or []:
            parsed = summarize_record(rec, division)
            all_records[parsed["id"]] = {**all_records.get(parsed["id"], {}), **parsed}
            if league_id == AL_ID:
                all_al[parsed["id"]] = {**all_al.get(parsed["id"], {}), **parsed}
            if standings_type == "wildCard" and league_id == AL_ID:
                wild_card.append(parsed)
            if standings_type == "regularSeason" and division == "American League East":
                al_east.append(parsed)
            if standings_type == "regularSeason" and parsed.get("divisionLeader"):
                division_leaders.append(parsed)

    al_east.sort(key=lambda t: t.get("divisionRank") or 99)
    wild_card.sort(key=lambda t: t.get("wildCardRank") or 99)

    jays = all_al.get(JAYS_ID) or next(t for t in wild_card if t["id"] == JAYS_ID)
    jays["hitting"] = pick_stat(hitting_by_id.get(JAYS_ID) or {}, HITTING_KEYS)
    jays["pitching"] = pick_stat(pitching_by_id.get(JAYS_ID) or {}, PITCHING_KEYS)
    jays["momentum"] = momentum_score(jays)

    # Bubble: WC field plus anyone within 6 GB of the last playoff spot.
    race = []
    for team in wild_card:
        gb = team.get("wildCardGamesBackNum")
        rank = team.get("wildCardRank") or 99
        if rank <= 8 or (gb is not None and gb <= 6) or team["id"] == JAYS_ID:
            enriched = dict(team)
            enriched["hitting"] = pick_stat(hitting_by_id.get(team["id"]) or {}, HITTING_KEYS)
            enriched["pitching"] = pick_stat(pitching_by_id.get(team["id"]) or {}, PITCHING_KEYS)
            enriched["momentum"] = momentum_score(enriched)
            race.append(enriched)

    race_ids = {team["id"] for team in race}
    race_ids.add(JAYS_ID)

    games_by_team: dict[int, list[dict]] = defaultdict(list)
    all_games = []
    for day in schedule.get("dates") or []:
        for game in day.get("games") or []:
            all_games.append(game)
            home_id = ((game.get("teams") or {}).get("home") or {}).get("team", {}).get("id")
            away_id = ((game.get("teams") or {}).get("away") or {}).get("team", {}).get("id")
            if home_id:
                games_by_team[home_id].append(game)
            if away_id:
                games_by_team[away_id].append(game)

    def upcoming_for(team_id: int, limit: int = 10) -> list[dict]:
        items = []
        for game in games_by_team.get(team_id, []):
            state = (game.get("status") or {}).get("abstractGameState")
            official = game.get("officialDate")
            if official and official < today.isoformat() and state == "Final":
                continue
            items.append(game_payload(game, team_id))
            if len(items) >= limit:
                break
        return items

    def recent_for(team_id: int, limit: int = 10) -> list[dict]:
        finals = []
        for game in games_by_team.get(team_id, []):
            if (game.get("status") or {}).get("abstractGameState") == "Final":
                finals.append(game_payload(game, team_id))
        return finals[-limit:]

    jays_upcoming = upcoming_for(JAYS_ID, 18)
    jays_recent = recent_for(JAYS_ID, 10)

    remaining_games = [
        game_payload(game, JAYS_ID)
        for game in games_by_team.get(JAYS_ID, [])
        if (game.get("status") or {}).get("abstractGameState") != "Final"
        or (game.get("officialDate") or "") >= today.isoformat()
    ]
    remaining_games = [
        g for g in remaining_games if g.get("abstractState") != "Final"
    ]
    opp_counter: Counter[str] = Counter()
    remaining_vs_race = 0
    strength_bits = []
    for game in remaining_games:
        opp = game.get("opponent") or {}
        label = opp.get("abbr") or opp.get("name")
        if label:
            opp_counter[label] += 1
        if opp.get("id") in race_ids and opp.get("id") != JAYS_ID:
            remaining_vs_race += 1
        rec = all_records.get(opp.get("id") or -1)
        if rec and rec.get("pct"):
            try:
                strength_bits.append(float(rec["pct"]))
            except (TypeError, ValueError):
                pass

    remaining_sos = round(sum(strength_bits) / len(strength_bits), 3) if strength_bits else None

    espn_teams = espn.get("injuries") or []
    il_fallback = []
    for player in jays_40man.get("roster") or []:
        status = player.get("status") or {}
        code = status.get("code") or ""
        if code.startswith("D") or "Injured" in (status.get("description") or ""):
            person = player.get("person") or {}
            il_fallback.append(
                {
                    "name": person.get("fullName"),
                    "status": status.get("description"),
                    "comment": player.get("note"),
                    "date": None,
                    "position": (player.get("position") or {}).get("abbreviation"),
                    "playerId": person.get("id"),
                }
            )

    jays_injuries = injury_items(
        match_espn_team(jays.get("name"), jays.get("abbr"), espn_teams),
        il_fallback,
    )
    jays["injuryCount"] = len(jays_injuries)

    for team in race:
        team["nextGames"] = upcoming_for(team["id"], 6)
        espn_team = match_espn_team(team.get("name"), team.get("abbr"), espn_teams)
        team["injuries"] = injury_items(espn_team, [])
        team["injuryCount"] = len(team["injuries"])
        if team["id"] in all_al:
            all_al[team["id"]]["injuryCount"] = team["injuryCount"]

    next_lookup = {team["id"]: team.get("nextGames") for team in race}
    for team in wild_card:
        team["nextGames"] = next_lookup.get(team["id"]) or upcoming_for(team["id"], 2)
    for team in al_east:
        if not team.get("nextGames"):
            team["nextGames"] = next_lookup.get(team["id"]) or upcoming_for(team["id"], 2)

    # Rooting board: next week of race-team games.
    rooting = []
    seen_games = set()
    week_end = (today + timedelta(days=8)).isoformat()
    for team in race:
        for game in games_by_team.get(team["id"], []):
            pk = game.get("gamePk")
            official = game.get("officialDate") or ""
            if pk in seen_games or official > week_end:
                continue
            if (game.get("status") or {}).get("abstractGameState") == "Final" and official < today.isoformat():
                continue
            seen_games.add(pk)
            payload = game_payload(game)
            home_id = payload["home"]["id"]
            away_id = payload["away"]["id"]
            if home_id not in race_ids and away_id not in race_ids:
                continue
            if JAYS_ID in (home_id, away_id):
                interest = "Jays game"
                note = "Get the W."
            elif home_id in race_ids and away_id in race_ids:
                interest = "Race game"
                note = "Bubble clash — one of these clubs has to lose."
            else:
                rival = payload["home"] if home_id in race_ids else payload["away"]
                rank = next((t.get("wildCardRank") for t in race if t["id"] == rival["id"]), 99)
                if rank and rank <= 3:
                    interest = "Need a loss"
                    note = f"Root against {rival.get('abbr')} — they are holding a wild-card spot."
                elif rank and rank < (jays.get("wildCardRank") or 99):
                    interest = "Need a loss"
                    note = f"A {rival.get('abbr')} loss trims the club Toronto is chasing."
                else:
                    interest = "Keep them down"
                    note = f"Do not let {rival.get('abbr')} sneak closer."
            rooting.append({**payload, "interest": interest, "note": note})
    rooting.sort(key=lambda g: g.get("gameDate") or "")

    roster, hitter_ids, pitcher_ids = active_roster_maps(jays_active)
    last_final = next((game for game in reversed(jays_recent) if game.get("gamePk")), None)
    last_batting = last_game_batting(last_final.get("gamePk") if last_final else None)
    hitters = build_hitters(jays_hitters, jays_hitters_l10, hitter_ids, roster, last_batting)
    pitchers = build_pitchers(jays_pitchers, jays_pitchers_l14, pitcher_ids, roster)

    prior = week_ago_map(week_ago_standings)
    apply_week_trends(wild_card, prior)
    apply_week_trends(race, prior)
    apply_week_trends(al_east, prior)
    apply_week_trends([jays], prior)

    playoff_odds = simulate_playoff_odds(all_al, all_records, all_games, jays_injuries)

    l14_hit = first_split_stat(team_hit_l14)
    l14_pitch = first_split_stat(team_pitch_l14)
    season_ops = float(jays.get("hitting", {}).get("ops") or 0) or None
    season_era = float(jays.get("pitching", {}).get("era") or 0) or None
    hot_ops = float(l14_hit.get("ops") or 0) if l14_hit.get("ops") else None
    hot_era = float(l14_pitch.get("era") or 0) if l14_pitch.get("era") else None
    ops_delta = round(hot_ops - season_ops, 3) if season_ops is not None and hot_ops is not None else None
    era_delta = round(hot_era - season_era, 2) if season_era is not None and hot_era is not None else None

    last10_rd = 0
    last10_wins = 0
    last10_losses = 0
    for game in jays_recent:
        us = game["home"]["score"] if game.get("isHome") else game["away"]["score"]
        them = game["away"]["score"] if game.get("isHome") else game["home"]["score"]
        if us is None or them is None:
            continue
        last10_rd += int(us) - int(them)
        if game.get("result") == "W":
            last10_wins += 1
        elif game.get("result") == "L":
            last10_losses += 1

    week = jays.get("weekAgo") or {}
    gb_delta = week.get("gbDelta")
    rank_delta = week.get("rankDelta")
    if gb_delta is not None and gb_delta < 0:
        gb_hint = f"{abs(gb_delta):.1f} closer than 7 days ago"
    elif gb_delta is not None and gb_delta > 0:
        gb_hint = f"{gb_delta:.1f} further back than 7 days ago"
    else:
        gb_hint = "Gap to the 3rd AL wild card"

    trends = {
        "windowDays": 7,
        "weekAgo": week,
        "gbDelta": gb_delta,
        "rankDelta": rank_delta,
        "last14": {
            "ops": l14_hit.get("ops"),
            "avg": l14_hit.get("avg"),
            "runs": l14_hit.get("runs"),
            "homeRuns": l14_hit.get("homeRuns"),
            "era": l14_pitch.get("era"),
            "whip": l14_pitch.get("whip"),
            "wins": l14_pitch.get("wins"),
            "losses": l14_pitch.get("losses"),
        },
        "last10": {
            "record": f"{last10_wins}-{last10_losses}",
            "runDifferential": last10_rd,
        },
        "opsDelta": ops_delta,
        "eraDelta": era_delta,
        "opsDirection": trend_dir(ops_delta, deadzone=0.015),
        "eraDirection": trend_dir(era_delta, invert=True, deadzone=0.15),
        "cards": [
            {
                "label": "Wild-card gap",
                "value": jays.get("wildCardGamesBack") or "—",
                "detail": gb_hint,
                "direction": week.get("direction") or "flat",
            },
            {
                "label": "WC rank",
                "value": f"#{jays.get('wildCardRank') or '—'}",
                "detail": (
                    f"Was #{week.get('wildCardRank')} a week ago"
                    if week.get("wildCardRank")
                    else "Among AL non-division leaders"
                ),
                "direction": trend_dir(rank_delta, invert=True, deadzone=0),
            },
            {
                "label": "Last 14 days",
                "value": f"{l14_pitch.get('wins', 0)}-{l14_pitch.get('losses', 0)}",
                "detail": "Record over the past two weeks",
                "direction": "up" if int(l14_pitch.get("wins") or 0) > int(l14_pitch.get("losses") or 0) else (
                    "down" if int(l14_pitch.get("wins") or 0) < int(l14_pitch.get("losses") or 0) else "flat"
                ),
            },
            {
                "label": "L10 run diff",
                "value": f"{last10_rd:+d}",
                "detail": f"{last10_wins}-{last10_losses} in the last 10",
                "direction": "up" if last10_rd > 0 else ("down" if last10_rd < 0 else "flat"),
            },
            {
                "label": "Offense (14d)",
                "value": l14_hit.get("ops") or "—",
                "detail": f"Season OPS {jays.get('hitting', {}).get('ops') or '—'}",
                "direction": trend_dir(ops_delta, deadzone=0.015),
                "stat": "OPS",
            },
            {
                "label": "Staff ERA (14d)",
                "value": l14_pitch.get("era") or "—",
                "detail": f"Season ERA {jays.get('pitching', {}).get('era') or '—'}",
                "direction": trend_dir(era_delta, invert=True, deadzone=0.15),
                "stat": "ERA",
            },
        ],
    }

    cut_team = next((t for t in wild_card if t.get("wildCardRank") == 3), None)
    ahead = [t for t in wild_card if (t.get("wildCardRank") or 99) < (jays.get("wildCardRank") or 99)]
    magic_number = wild_card_magic(jays, wild_card)

    payload = {
        "generatedAt": now.isoformat(),
        "season": season,
        "source": "MLB Stats API + ESPN injuries",
        "jays": jays,
        "narrative": narrative_for(jays),
        "alEast": al_east,
        "wildCard": wild_card[:10],
        "divisionLeaders": [
            {
                "id": t["id"],
                "name": t["name"],
                "teamName": t["teamName"],
                "abbr": t["abbr"],
                "logo": t["logo"],
                "color": t["color"],
                "wins": t["wins"],
                "losses": t["losses"],
                "pct": t["pct"],
                "divisionName": t.get("divisionName"),
            }
            for t in division_leaders
            if t.get("id") in all_al
        ],
        "cutLine": {
            "team": cut_team,
            "jaysGamesBack": jays.get("wildCardGamesBack"),
            "teamsAhead": len(ahead),
        },
        "magicNumber": magic_number,
        "race": race,
        "schedule": jays_upcoming,
        "recent": jays_recent,
        "remaining": {
            "games": len(remaining_games),
            "vsRace": remaining_vs_race,
            "opponents": [{"abbr": k, "games": v} for k, v in opp_counter.most_common()],
            "strengthOfSchedule": remaining_sos,
        },
        "rooting": rooting[:18],
        "injuries": jays_injuries,
        "roster": {
            "count": len(roster),
            "asOf": today.isoformat(),
        },
        "leaders": {
            "hitting": hitters,
            "pitching": pitchers,
        },
        "trends": trends,
        "playoffOdds": playoff_odds,
        "kpis": [
            {"label": "Wild Card GB", "value": jays.get("wildCardGamesBack") or "—", "hint": gb_hint, "trend": week.get("direction"), "stat": "GB"},
            {"label": "WC Rank", "value": f"#{jays.get('wildCardRank') or '—'}", "hint": "Among AL non-division leaders", "trend": trend_dir(rank_delta, invert=True, deadzone=0), "stat": "WC"},
            {"label": "Last 10", "value": jays.get("lastTen") or "—", "hint": "Are they getting hot?", "stat": "L10"},
            {"label": "Streak", "value": jays.get("streak") or "—", "hint": "Current run"},
            {"label": "Run Diff", "value": f"{jays.get('runDifferential'):+d}", "hint": f"L10 margin {last10_rd:+d}", "trend": "up" if last10_rd > 0 else ("down" if last10_rd < 0 else "flat")},
            {"label": "WC Elim #", "value": jays.get("wildCardEliminationNumber") or "—", "hint": "Jays losses + rival wins that ends it", "stat": "Elim"},
            {"label": "Games left", "value": str(jays.get("gamesRemaining") or len(remaining_games)), "hint": "Out of 162"},
            {"label": "Pythag W-L", "value": f"{jays.get('pythagWins')}-{jays.get('pythagLosses')}", "hint": "Record the run differential expects", "stat": "Pythag"},
        ],
    }

    OUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {OUT_PATH} at {payload['generatedAt']}")
    print(
        f"Jays {jays['wins']}-{jays['losses']}  WC#{jays.get('wildCardRank')}  "
        f"GB {jays.get('wildCardGamesBack')}  L10 {jays.get('lastTen')}  {jays.get('streak')}  "
        f"odds {playoff_odds.get('percent')}%"
    )


if __name__ == "__main__":
    main()
