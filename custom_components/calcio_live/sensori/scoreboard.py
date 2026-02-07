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
    
def process_match_data(data, hass, team_name=None, next_match_only=False, start_date=None, end_date=None):
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
            clock = match.get("status", {}).get("displayClock", "N/A")
            period = match.get("status", {}).get("period", "N/A")
            venue = competitions[0].get("venue", {}).get("fullName", "N/A")
            match_details = _get_details(competitions[0].get("details", []))

            if team_name and (team_name.lower() in home_team.lower() or team_name.lower() in away_team.lower()):
                team_logo = home_logo if team_name.lower() in home_team.lower() else away_logo

            match_data = {
                "date": _parse_date(hass, match.get("date")),
                "season_info": season_info, #per il mixed
                "league_name": league_name,  # ← NUOVO: Nome della competizione
                "home_team": home_team,
                "home_logo": home_logo,
                "home_form": home_form,
                "home_score": home_score,
                "home_statistics": home_statistics,
                "away_team": away_team,
                "away_logo": away_logo,
                "away_form": away_form,
                "away_score": away_score,
                "away_statistics": away_statistics,
                "state": match_state,
                "status": match_status,
                "clock": clock,
                "period": period,
                "venue": venue,
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

            # Priorità 2: Partite terminate entro 48 ore
            recent_finished_matches = [m for m in matches
                if m["state"] == "post" and is_within_last_48_hours(m["date"])
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

def is_within_last_48_hours(end_time):
    try:
        # Converte la stringa formattata in oggetto datetime
        if isinstance(end_time, str):
            end_time_dt = datetime.strptime(end_time, "%d/%m/%Y %H:%M").replace(tzinfo=timezone.utc)
        elif isinstance(end_time, datetime):
            end_time_dt = end_time
        else:
            raise ValueError("La data fornita non è né una stringa né un oggetto datetime")
        
        # Ottiene l'orario attuale con timezone UTC
        current_time = datetime.now(timezone.utc)
        
        # Confronta l'intervallo di 48 ore
        return current_time - end_time_dt <= timedelta(hours=48)
    except Exception as e:
        _LOGGER.error(f"Errore nel calcolo dell'intervallo di 48 ore: {e}")
        return False

def _get_statistics(competitor):
    statistics = {}
    stats = competitor.get("statistics", [])
    for stat in stats:
        stat_name = stat.get("name", "Unknown")
        stat_value = stat.get("displayValue", "N/A")
        statistics[stat_name] = stat_value
    return statistics

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