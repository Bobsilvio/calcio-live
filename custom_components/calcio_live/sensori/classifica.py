from .const import _LOGGER
from dateutil import parser

def classifica_data(data):
    try:
        standings_list = []

        for child in data.get("children", []):
            standings_data = child.get("standings", {}).get("entries", [])
            standings = []

            for index, entry in enumerate(standings_data, start=1):
                team = entry.get("team", {}) or {}
                stats = {
                    stat.get("name"): stat.get("displayValue")
                    for stat in entry.get("stats", []) or []
                }

                rank = (entry.get("note") or {}).get("rank", index)

                team_data = {
                    "rank": rank,
                    "team_id": team.get("id"),
                    "team_name": team.get("displayName"),
                    "team_logo": _get_logo(team),
                    "points": stats.get("points", "N/A"),
                    "games_played": stats.get("gamesPlayed", "N/A"),
                    "wins": stats.get("wins", "N/A"),
                    "draws": stats.get("ties", "N/A"),
                    "losses": stats.get("losses", "N/A"),
                    "goals_for": stats.get("pointsFor", "N/A"),
                    "goals_against": stats.get("pointsAgainst", "N/A"),
                    "goal_difference": stats.get("pointDifferential", "N/A")
                }
                standings.append(team_data)

            full_table_link = child.get("standings", {}).get("links", [])[0].get("href", "N/A") if child.get("standings", {}).get("links") else "N/A"

            standings_list.append({
                "name": child.get("name", "Unknown"),
                "standings": standings,
                "full_table_link": full_table_link
            })

        # La stagione corrente sta nel campo "season" a livello top. Prima
        # veniva cercata in "seasons" con l'anno 2024 scritto a mano: dal 2025
        # in poi non trovava più nulla e season/season_start/season_end
        # restavano "N/A". Come fallback prendiamo l'anno più recente.
        current_season = data.get("season") or {}
        if not current_season:
            seasons_data = data.get("seasons", []) or []
            current_season = max(
                seasons_data, key=lambda s: s.get("year", 0), default=None
            )

        season_display_name = current_season.get("displayName", "N/A") if current_season else "N/A"
        season_start = _parse_date(current_season.get("startDate", "N/A")) if current_season else None
        season_end = _parse_date(current_season.get("endDate", "N/A")) if current_season else None

        return {
            "season": season_display_name,
            "season_start": season_start,
            "season_end": season_end,
            "standings_groups": standings_list  # Mantiene le classifiche separate
        }
    except Exception as e:
        _LOGGER.error(f"Errore nel processare i dati della classifica: {e}")
        return {}



def _get_logo(team):
    """Alcune squadre non hanno loghi (es. Torreense in Europa League): prima
    l'indice [0] sollevava IndexError e faceva fallire l'INTERA classifica,
    che tornava {} e riprovava a ogni update."""
    logos = team.get("logos") or []
    if logos:
        return logos[0].get("href")
    return None


def _parse_date(date_str):
    try:
        parsed_date = parser.isoparse(date_str)
        return parsed_date.strftime("%d-%m-%Y")
    except (ValueError, TypeError) as e:
        _LOGGER.error(f"Errore nel parsing della data {date_str}: {e}")
        return None