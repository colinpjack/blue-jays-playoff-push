#!/usr/bin/env python3
"""Fetch Blue Jays playoff-race data and write data.json for GitHub Pages."""

from __future__ import annotations

import json
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

    for team in race:
        team["nextGames"] = upcoming_for(team["id"], 6)
        espn_team = match_espn_team(team.get("name"), team.get("abbr"), espn_teams)
        team["injuries"] = injury_items(espn_team, [])
        team["injuryCount"] = len(team["injuries"])

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

    def leader_rows(payload: dict, group: str) -> list[dict]:
        splits = (payload.get("stats") or [{}])[0].get("splits") or []
        rows = []
        for split in splits:
            player = split.get("player") or {}
            stat = split.get("stat") or {}
            pid = player.get("id")
            if group == "hitting":
                pa = int(stat.get("plateAppearances") or 0)
                if pa < 120:
                    continue
                rows.append(
                    {
                        "id": pid,
                        "name": player.get("fullName"),
                        "headshot": f"https://img.mlbstatic.com/mlb-photos/image/upload/d_people:generic:headshot:67:current.png/w_180,q_auto:best/v1/people/{pid}/headshot/67/current",
                        "avg": stat.get("avg"),
                        "obp": stat.get("obp"),
                        "slg": stat.get("slg"),
                        "ops": stat.get("ops"),
                        "hr": stat.get("homeRuns"),
                        "rbi": stat.get("rbi"),
                        "sb": stat.get("stolenBases"),
                        "hits": stat.get("hits"),
                        "pa": pa,
                    }
                )
            else:
                ip = str(stat.get("inningsPitched") or "0")
                try:
                    ip_val = float(ip)
                except ValueError:
                    ip_val = 0.0
                gs = int(stat.get("gamesStarted") or 0)
                if ip_val < 15 and int(stat.get("saves") or 0) < 5:
                    continue
                rows.append(
                    {
                        "id": pid,
                        "name": player.get("fullName"),
                        "headshot": f"https://img.mlbstatic.com/mlb-photos/image/upload/d_people:generic:headshot:67:current.png/w_180,q_auto:best/v1/people/{pid}/headshot/67/current",
                        "era": stat.get("era"),
                        "whip": stat.get("whip"),
                        "ip": stat.get("inningsPitched"),
                        "w": stat.get("wins"),
                        "l": stat.get("losses"),
                        "so": stat.get("strikeOuts"),
                        "sv": stat.get("saves"),
                        "gs": gs,
                        "k9": stat.get("strikeoutsPer9Inn"),
                        "role": "SP" if gs >= 5 else "RP",
                    }
                )
        injured_names = {item.get("name") for item in jays_injuries if item.get("name")}
        rows = [row for row in rows if row.get("name") not in injured_names]
        featured_hitters = {
            "Vladimir Guerrero Jr.",
            "George Springer",
            "Kazuma Okamoto",
            "Ernie Clement",
            "Alejandro Kirk",
            "Andrés Giménez",
        }
        featured_pitchers = {
            "Dylan Cease",
            "Kevin Gausman",
            "Shane Bieber",
            "Louis Varland",
            "Tyler Rogers",
        }
        if group == "hitting":
            rows.sort(key=lambda r: float(r.get("ops") or 0), reverse=True)
            top = rows[:5]
            have = {row.get("name") for row in top}
            for row in rows:
                if row.get("name") in featured_hitters and row.get("name") not in have:
                    top.append(row)
                    have.add(row.get("name"))
                if len(top) >= 8:
                    break
            return top
        rows.sort(key=lambda r: (0 if r["role"] == "SP" else 1, float(r.get("era") or 99)))
        top = []
        have = set()
        for row in [r for r in rows if r.get("name") in featured_pitchers] + rows:
            if row["id"] in have:
                continue
            have.add(row["id"])
            top.append(row)
            if len(top) >= 6:
                break
        return top

    cut_team = next((t for t in wild_card if t.get("wildCardRank") == 3), None)
    ahead = [t for t in wild_card if (t.get("wildCardRank") or 99) < (jays.get("wildCardRank") or 99)]

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
        "leaders": {
            "hitting": leader_rows(jays_hitters, "hitting"),
            "pitching": leader_rows(jays_pitchers, "pitching"),
        },
        "kpis": [
            {"label": "Wild Card GB", "value": jays.get("wildCardGamesBack") or "—", "hint": "Gap to the 3rd AL wild card"},
            {"label": "WC Rank", "value": f"#{jays.get('wildCardRank') or '—'}", "hint": "Among AL non-division leaders"},
            {"label": "Last 10", "value": jays.get("lastTen") or "—", "hint": "Are they getting hot?"},
            {"label": "Streak", "value": jays.get("streak") or "—", "hint": "Current run"},
            {"label": "Run Diff", "value": f"{jays.get('runDifferential'):+d}", "hint": "Season scoring margin"},
            {"label": "WC Elim #", "value": jays.get("wildCardEliminationNumber") or "—", "hint": "Combination of Jays losses + rival wins that ends it"},
            {"label": "Games left", "value": str(jays.get("gamesRemaining") or len(remaining_games)), "hint": "Out of 162"},
            {"label": "Pythag W-L", "value": f"{jays.get('pythagWins')}-{jays.get('pythagLosses')}", "hint": "Record the run differential expects"},
        ],
    }

    OUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {OUT_PATH} at {payload['generatedAt']}")
    print(
        f"Jays {jays['wins']}-{jays['losses']}  WC#{jays.get('wildCardRank')}  "
        f"GB {jays.get('wildCardGamesBack')}  L10 {jays.get('lastTen')}  {jays.get('streak')}"
    )


if __name__ == "__main__":
    main()
