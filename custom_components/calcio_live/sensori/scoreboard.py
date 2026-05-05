from .const import _LOGGER
from dateutil import parser
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta, timezone

def process_league_data(data, hass=None):
    try:
        leagues_data = data.get("leagues", [])
        league_info = []

        for league in leagues_data:
            league_abbreviation = league.get("abbreviation", "N/A")
            league_start_date = league.get("season", {}).get("startDate", "N/A")
            league_end_date = league.get("season", {}).get("endDate", "N/A")
            
            logos = league.get("logos", [])
            logo_href = logos[0].get("href", "N/A") if logos else "N/A"
            
            league_info.append({
                "abbreviation": league_abbreviation,
                "startDate": _parse_date(hass, league_start_date, show_time=False),
                "endDate": _parse_date(hass, league_end_date, show_time=False),
                "logo_href": logo_href
            })

        return league_info

    except Exception as e:
        _LOGGER.error(f"Errore nel processare i dati della lega: {e}")
        return []

def get_season_slug_or_displayname(match):
    season_data = match.get("season", {})
    
    # Controlla prima per 'slug', se esiste
    slug = season_data.get("slug")
    if slug:
        return slug
    
    # Se non trova 'slug', prova a prendere 'displayName'
    display_name = season_data.get("displayName")
    return display_name
    
def process_match_data(data, hass, team_name=None, next_match_only=False, start_date=None, end_date=None, recent_match_hours=24):
    try:
        matches_data = data.get("events", [])
        league_info = process_league_data(data, hass)
        matches = []
        team_logo = None

        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)

        for match in matches_data:
            match_name = match.get("name", "").lower()
            if team_name and team_name.lower() not in match_name:
                continue

            match_date_str = match.get("date", "")

            try:
                match_date = parser.isoparse(match_date_str).astimezone(timezone.utc) if match_date_str else None
            except ValueError:
                _LOGGER.error(f"Errore nel parsing della data della partita: {match_date_str}")
                continue

            if start_date and match_date and match_date < start_date:
                continue
            if end_date and match_date and match_date > end_date:
                continue
            
            #Solo per il mixed
            season_info = get_season_slug_or_displayname(match)

            competitions = match.get("competitions", [])
            # Estrai il nome della lega/competizione
            league_name = competitions[0].get("league", {}).get("displayName", "N/A") if competitions else "N/A"
            
            competitors = competitions[0].get("competitors", []) if competitions else []

            home_team_data = competitors[0].get("team", {})
            home_team = home_team_data.get("displayName", "N/A")
            home_logo = home_team_data.get("logo", None)
            if not home_logo:
                home_logos = home_team_data.get("logos", [{}])
                home_logo = home_logos[0].get("href", "N/A")
            home_form = competitors[0].get("form", "N/A")
            home_score = competitors[0].get("score", "N/A")
            home_statistics = _get_statistics(competitors[0])

            away_team_data = competitors[1].get("team", {})
            away_team = away_team_data.get("displayName", "N/A")
            away_logo = away_team_data.get("logo", None)
            if not away_logo:
                away_logos = away_team_data.get("logos", [{}])
                away_logo = away_logos[0].get("href", "N/A")
            away_form = competitors[1].get("form", "N/A")
            away_score = competitors[1].get("score", "N/A")
            away_statistics = _get_statistics(competitors[1])

            status_type = match.get("status", {}).get("type", {})
            match_state = status_type.get("state", "N/A")
            match_status = status_type.get("description", "N/A")
            status_detail = status_type.get("detail", "N/A")
            clock = match.get("status", {}).get("displayClock", "N/A")
            period = match.get("status", {}).get("period", "N/A")

            venue_obj = competitions[0].get("venue", {}) or {}
            venue = venue_obj.get("fullName", "N/A")
            venue_address = venue_obj.get("address", {}) or {}
            venue_city = venue_address.get("city", "N/A")
            venue_country = venue_address.get("country", "N/A")

            home_abbrev = home_team_data.get("abbreviation", "N/A")
            home_color = home_team_data.get("color", "N/A")
            home_record = _get_record(competitors[0])
            home_top_scorer = _get_top_scorer(competitors[0])

            away_abbrev = away_team_data.get("abbreviation", "N/A")
            away_color = away_team_data.get("color", "N/A")
            away_record = _get_record(competitors[1])
            away_top_scorer = _get_top_scorer(competitors[1])

            broadcast = _get_broadcast(competitions[0])
            attendance = competitions[0].get("attendance", 0)

            match_details = _get_details(competitions[0].get("details", []))

            if team_name and (team_name.lower() in home_team.lower() or team_name.lower() in away_team.lower()):
                team_logo = home_logo if team_name.lower() in home_team.lower() else away_logo

            match_data = {
                "event_id": match.get("id"),
                "date": _parse_date(hass, match.get("date")),
                "season_info": season_info, #per il mixed
                "league_name": league_name,  # ← NUOVO: Nome della competizione
                "home_team": home_team,
                "home_abbrev": home_abbrev,
                "home_color": home_color,
                "home_logo": home_logo,
                "home_form": home_form,
                "home_score": home_score,
                "home_statistics": home_statistics,
                "home_record": home_record,
                "home_top_scorer": home_top_scorer,
                "away_team": away_team,
                "away_abbrev": away_abbrev,
                "away_color": away_color,
                "away_logo": away_logo,
                "away_form": away_form,
                "away_score": away_score,
                "away_statistics": away_statistics,
                "away_record": away_record,
                "away_top_scorer": away_top_scorer,
                "state": match_state,
                "status": match_status,
                "status_detail": status_detail,
                "clock": clock,
                "period": period,
                "venue": venue,
                "venue_city": venue_city,
                "venue_country": venue_country,
                "broadcast": broadcast,
                "attendance": attendance,
                "match_details": match_details,
            }
            matches.append(match_data)

        if next_match_only:
            # Priorità 1: Partite in corso
            live_matches = [m for m in matches if m["state"] == "in"]
            if live_matches:
                return {
                    "league_info": league_info,
                    "team_name": team_name if team_name else "Tutte le partite",
                    "team_logo": team_logo if team_logo else "N/A",
                    "matches": [live_matches[0]]
                }

            # Priorità 2: Partite terminate entro la finestra configurata (default 48h)
            recent_finished_matches = [m for m in matches
                if m["state"] == "post" and is_within_recent_window(m["date"], recent_match_hours)
            ]
            
            if recent_finished_matches:
                return {
                    "league_info": league_info,
                    "team_name": team_name if team_name else "Tutte le partite",
                    "team_logo": team_logo if team_logo else "N/A",
                    "matches": [recent_finished_matches[0]]
                }

            # Priorità 3: Prossime partite
            upcoming_matches = [m for m in matches if m["state"] == "pre"]
            if upcoming_matches:
                return {
                    "league_info": league_info,
                    "team_name": team_name if team_name else "Tutte le partite",
                    "team_logo": team_logo if team_logo else "N/A",
                    "matches": [upcoming_matches[0]]
                }
                
        return {
            "league_info": league_info,
            "team_name": team_name if team_name else "Tutte le partite",
            "team_logo": team_logo if team_logo else "N/A",
            "matches": matches
        }

    except Exception as e:
        _LOGGER.error(f"Errore nel processare i dati delle partite: {e}")
        return {}

def is_within_recent_window(end_time, hours=24):
    """Ritorna True se la partita (kickoff) è avvenuta entro le ultime `hours`."""
    try:
        if isinstance(end_time, str):
            end_time_dt = datetime.strptime(end_time, "%d/%m/%Y %H:%M").replace(tzinfo=timezone.utc)
        elif isinstance(end_time, datetime):
            end_time_dt = end_time
        else:
            raise ValueError("La data fornita non è né una stringa né un oggetto datetime")
        current_time = datetime.now(timezone.utc)
        return current_time - end_time_dt <= timedelta(hours=hours)
    except Exception as e:
        _LOGGER.error(f"Errore nel calcolo dell'intervallo recente ({hours}h): {e}")
        return False

# Backwards-compat alias
def is_within_last_48_hours(end_time):
    return is_within_recent_window(end_time, 48)

def _get_statistics(competitor):
    statistics = {}
    stats = competitor.get("statistics", [])
    for stat in stats:
        stat_name = stat.get("name", "Unknown")
        stat_value = stat.get("displayValue", "N/A")
        statistics[stat_name] = stat_value
    return statistics

def _get_record(competitor):
    """Restituisce il record stagionale della squadra (es. '14-6-14' = V-N-P)."""
    records = competitor.get("records", []) or []
    if records:
        return records[0].get("summary", "")
    return ""

def _get_top_scorer(competitor):
    """Restituisce il capocannoniere della squadra: {name, short_name, value}."""
    leaders = competitor.get("leaders", []) or []
    for ldr in leaders:
        if ldr.get("name") == "goals":
            tops = ldr.get("leaders", []) or []
            if tops:
                t = tops[0]
                athlete = t.get("athlete", {}) or {}
                return {
                    "name": athlete.get("displayName", ""),
                    "short_name": athlete.get("shortName", ""),
                    "value": t.get("displayValue", ""),
                }
    return None

def _get_broadcast(competition):
    """Restituisce il primo canale TV/streaming disponibile."""
    gbs = competition.get("geoBroadcasts", []) or []
    if gbs:
        media = gbs[0].get("media", {}) or {}
        return media.get("shortName", "")
    return ""

def process_summary_data(data):
    """Estrae lineup, formazioni, key events e head-to-head dal summary endpoint.
    Restituisce un dict con: lineup_home, lineup_away, formation_home, formation_away,
    key_events, head_to_head."""
    out = {
        "lineup_home": [],
        "lineup_away": [],
        "formation_home": "",
        "formation_away": "",
        "key_events": [],
        "head_to_head": [],
    }
    try:
        rosters = data.get("rosters", []) or []
        for r in rosters:
            home_away = r.get("homeAway", "")
            formation = r.get("formation", "")
            roster = r.get("roster", []) or []
            players = []
            for p in roster:
                a = p.get("athlete", {}) or {}
                players.append({
                    "id": a.get("id", ""),
                    "name": a.get("displayName", ""),
                    "short_name": a.get("shortName", ""),
                    "jersey": p.get("jersey", ""),
                    "position": (p.get("position", {}) or {}).get("abbreviation", ""),
                    "starter": p.get("starter", False),
                    "headshot": (a.get("headshot", {}) or {}).get("href", ""),
                })
            if home_away == "home":
                out["lineup_home"] = players
                out["formation_home"] = formation
            elif home_away == "away":
                out["lineup_away"] = players
                out["formation_away"] = formation

        key_events = data.get("keyEvents", []) or []
        for ev in key_events:
            t = ev.get("type", {}) or {}
            clock = (ev.get("clock", {}) or {}).get("displayValue", "")
            team = (ev.get("team", {}) or {}).get("displayName", "")
            participants = ev.get("participants", []) or []
            athletes = []
            for p in participants:
                a = p.get("athlete", {}) or {}
                athletes.append(a.get("displayName", ""))
            out["key_events"].append({
                "type": t.get("type", ""),
                "type_text": t.get("text", ""),
                "text": ev.get("text", ""),
                "short_text": ev.get("shortText", ""),
                "clock": clock,
                "team": team,
                "athletes": athletes,
                "scoring_play": ev.get("scoringPlay", False),
            })

        h2h = data.get("headToHeadGames", []) or []
        for game in h2h:
            events = game.get("events", []) or []
            for e in events[:10]:
                comp = (e.get("competitions", []) or [{}])[0]
                competitors = comp.get("competitors", []) or []
                if len(competitors) < 2:
                    continue
                home_c = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0])
                away_c = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1])
                out["head_to_head"].append({
                    "date": e.get("date", ""),
                    "home_team": (home_c.get("team", {}) or {}).get("displayName", ""),
                    "home_logo": (home_c.get("team", {}) or {}).get("logo", ""),
                    "home_score": home_c.get("score", ""),
                    "away_team": (away_c.get("team", {}) or {}).get("displayName", ""),
                    "away_logo": (away_c.get("team", {}) or {}).get("logo", ""),
                    "away_score": away_c.get("score", ""),
                })
    except Exception as e:
        _LOGGER.error(f"Errore nel processare summary: {e}")
    return out

def process_news_data(data):
    """Estrae lista articoli dal news endpoint."""
    articles = []
    try:
        items = data.get("articles", []) or []
        for a in items:
            images = a.get("images", []) or []
            img = images[0].get("url", "") if images else ""
            categories = a.get("categories", []) or []
            cat_name = ""
            for c in categories:
                if c.get("type") == "league":
                    cat_name = c.get("description", "") or (c.get("league", {}) or {}).get("description", "")
                    break
            articles.append({
                "headline": a.get("headline", ""),
                "description": a.get("description", ""),
                "published": a.get("published", ""),
                "image": img,
                "link": (a.get("links", {}) or {}).get("web", {}).get("href", "") or a.get("link", ""),
                "category": cat_name,
                "type": a.get("type", ""),
            })
    except Exception as e:
        _LOGGER.error(f"Errore nel processare news: {e}")
    return articles

def _get_details(details):
    events = []
    for detail in details:
        event_type = detail.get("type", {}).get("text", "Unknown")
        clock = detail.get("clock", {}).get("displayValue", "N/A")
        athletes = [athlete.get("displayName", "Unknown") for athlete in detail.get("athletesInvolved", [])]
        athletes_str = ", ".join(athletes) if athletes else "N/A"
        events.append(f"{event_type} - {clock}: {athletes_str}")
    return events

def _parse_date(hass, date_str, show_time=True):
    try:
        user_timezone = hass.config.time_zone
        parsed_date = parser.isoparse(date_str).replace(tzinfo=timezone.utc)
        local_tz = ZoneInfo(user_timezone)
        local_date = parsed_date.astimezone(local_tz)

        if show_time:
            return local_date.strftime("%d/%m/%Y %H:%M")
        else:
            return local_date.strftime("%d/%m/%Y")
    except (ValueError, TypeError) as e:
        #_LOGGER.error(f"Errore nel parsing della data {date_str}: {e}")
        return "N/A"