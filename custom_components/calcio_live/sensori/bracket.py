"""Processing del tabellone (knockout bracket) per competizioni a eliminazione diretta.

ESPN espone le partite KO nel solito endpoint /scoreboard ma le distingue tramite
note del tipo "1st Leg" / "2nd Leg - X advance Y-Z on aggregate". Qui le raggruppiamo
in tie (andata + ritorno) e in round (Round of 16 / Quarterfinals / Semifinals / Final).

Etichette in inglese (standard internazionale football). La card può aggiungere
una traduzione localizzata.
"""

from .const import _LOGGER
import re

# Etichetta del round in base al numero di tie. Si nomina dal più piccolo (Final)
# salendo. UCL 2024-26 ha anche un Knockout Playoff Round prima dell'R16: lo
# riconosciamo perché c'è un secondo round da 8 tie che NON è R16 (l'R16 è il
# penultimo da 8).
DEFAULT_NAMES = {
    1: "Final",
    2: "Semifinals",
    4: "Quarterfinals",
    8: "Round of 16",
    16: "Round of 32",
}
ITALIAN_NAMES = {
    1: "Finale",
    2: "Semifinali",
    4: "Quarti di finale",
    8: "Ottavi di finale",
    16: "Sedicesimi",
}


def _parse_aggregate(note_text):
    """Estrae info dal testo del 2nd leg: '2nd Leg - X advance Y-Z on aggregate'.
    Ritorna dict {winner_team, agg_for, agg_against, tied} oppure None.
    """
    if not note_text:
        return None
    if "Tied on aggregate" in note_text:
        return {"winner_team": None, "agg_for": None, "agg_against": None, "tied": True}
    m = re.search(r"2nd Leg\s*-\s*(.+?)\s+(?:advance|lead)\s+(\d+)\s*-\s*(\d+)\s+on aggregate", note_text)
    if m:
        return {
            "winner_team": m.group(1).strip(),
            "agg_for": int(m.group(2)),
            "agg_against": int(m.group(3)),
            "tied": False,
        }
    return None


def _safe_int(v):
    try:
        return int(v)
    except (ValueError, TypeError):
        return None


def process_bracket_data(data):
    """Estrae il bracket dai dati di /scoreboard di una fase KO.
    Restituisce {rounds: [{name, ties: [...]}], updated_at}.
    """
    out = {"rounds": [], "ties_count": 0}
    try:
        events = data.get("events", []) or []
        ties = {}  # key: frozenset(id1, id2) → tie dict

        for e in events:
            comps = e.get("competitions", []) or []
            if not comps:
                continue
            c = comps[0]
            notes = c.get("notes", []) or []
            note_text = ""
            if notes:
                note_text = notes[0].get("headline", "") or notes[0].get("text", "") or ""
            is_first_leg = "1st Leg" in note_text
            is_second_leg = "2nd Leg" in note_text
            is_final_single = (not is_first_leg and not is_second_leg) and "Final" in note_text
            # se non riconosciuto come leg KO, skip (potrebbero essere league phase residui)
            if not (is_first_leg or is_second_leg or is_final_single):
                continue

            competitors = c.get("competitors", []) or []
            home = next((x for x in competitors if x.get("homeAway") == "home"), None)
            away = next((x for x in competitors if x.get("homeAway") == "away"), None)
            if not home or not away:
                continue

            home_team = (home.get("team") or {}).get("displayName", "")
            away_team = (away.get("team") or {}).get("displayName", "")
            home_id = (home.get("team") or {}).get("id", "")
            away_id = (away.get("team") or {}).get("id", "")
            home_logo = (home.get("team") or {}).get("logo", "")
            away_logo = (away.get("team") or {}).get("logo", "")
            home_abbrev = (home.get("team") or {}).get("abbreviation", "")
            away_abbrev = (away.get("team") or {}).get("abbreviation", "")

            tie_key = frozenset([home_id, away_id])
            if tie_key not in ties:
                ties[tie_key] = {
                    "team_a": {"name": "", "logo": "", "abbrev": "", "id": ""},
                    "team_b": {"name": "", "logo": "", "abbrev": "", "id": ""},
                    "leg1": None,
                    "leg2": None,
                    "single": None,
                    "first_leg_date": None,
                    "winner_team": None,
                    "aggregate": None,
                    "tied": False,
                    "completed": False,
                }
            tie = ties[tie_key]

            # Solo i campi consumati dalla Bracket card: per ogni leg la card legge
            # home_team/away_team/home_score/away_score/state (i loghi/abbrev li prende
            # da team_a/team_b, non dal leg). Loghi/abbrev/status/venue/event_id per leg
            # sono ESPN raw inutilizzati → omessi per restare sotto i 16384 byte del recorder.
            leg_payload = {
                "home_team": home_team,
                "home_score": _safe_int(home.get("score")),
                "away_team": away_team,
                "away_score": _safe_int(away.get("score")),
                "date": e.get("date", ""),
                "state": ((e.get("status") or {}).get("type") or {}).get("state", ""),
            }

            if is_first_leg:
                tie["leg1"] = leg_payload
                tie["first_leg_date"] = e.get("date", "")
                # Inizializza team_a/b dalla prima leg vista (home della 1st leg = team_a)
                if not tie["team_a"]["name"]:
                    tie["team_a"] = {"name": home_team, "logo": home_logo, "abbrev": home_abbrev, "id": home_id}
                    tie["team_b"] = {"name": away_team, "logo": away_logo, "abbrev": away_abbrev, "id": away_id}
            elif is_second_leg:
                tie["leg2"] = leg_payload
                agg = _parse_aggregate(note_text)
                if agg:
                    tie["winner_team"] = agg.get("winner_team")
                    tie["aggregate"] = (
                        f"{agg.get('agg_for')}-{agg.get('agg_against')}"
                        if agg.get("agg_for") is not None else None
                    )
                    tie["tied"] = agg.get("tied", False)
                    tie["completed"] = leg_payload["state"] == "post"
                # Se non abbiamo ancora team_a (capita se 1st leg è prima che facciamo update),
                # popoliamolo invertendo (la 2nd leg ha home/away invertiti rispetto alla 1st)
                if not tie["team_a"]["name"]:
                    tie["team_a"] = {"name": away_team, "logo": away_logo, "abbrev": away_abbrev, "id": away_id}
                    tie["team_b"] = {"name": home_team, "logo": home_logo, "abbrev": home_abbrev, "id": home_id}
            elif is_final_single:
                tie["single"] = leg_payload
                tie["first_leg_date"] = e.get("date", "")
                if not tie["team_a"]["name"]:
                    tie["team_a"] = {"name": home_team, "logo": home_logo, "abbrev": home_abbrev, "id": home_id}
                    tie["team_b"] = {"name": away_team, "logo": away_logo, "abbrev": away_abbrev, "id": away_id}
                # Determina vincitore se completata
                hs, as_ = leg_payload["home_score"], leg_payload["away_score"]
                if leg_payload["state"] == "post" and hs is not None and as_ is not None:
                    tie["completed"] = True
                    if hs > as_:
                        tie["winner_team"] = home_team
                    elif as_ > hs:
                        tie["winner_team"] = away_team
                    else:
                        tie["tied"] = True

        # Ordino i tie per data della 1st leg (o single)
        sorted_ties = sorted(
            ties.values(),
            key=lambda t: t.get("first_leg_date") or t.get("leg2", {}).get("date", "") if t.get("leg2") else "",
        )

        # Raggruppo i tie in round per data: tie con date vicine appartengono allo stesso round.
        # Strategia semplice: cluster sequenziali, dove un nuovo round inizia se la differenza
        # con il tie precedente è > 5 giorni.
        from datetime import datetime
        groups = []
        current = []
        prev_date = None

        def parse_iso(s):
            if not s:
                return None
            try:
                return datetime.strptime(s[:10], "%Y-%m-%d")
            except Exception:
                return None

        for tie in sorted_ties:
            d = parse_iso(tie.get("first_leg_date") or "")
            if prev_date is None or d is None or (d - prev_date).days <= 7:
                current.append(tie)
            else:
                groups.append(current)
                current = [tie]
            if d is not None:
                prev_date = d
        if current:
            groups.append(current)

        # Calcolo size (potenza di 2) di ciascun gruppo cronologico
        sized_rounds = []
        for g in groups:
            size = 1
            while size < len(g):
                size *= 2
            sized_rounds.append({"size": size, "ties": g})

        # Etichettatura: vado a ritroso (dal round più recente al più vecchio).
        # Tengo traccia della "size attesa" che parte dalla size dell'ultimo round
        # e raddoppia ad ogni step indietro (perché un torneo a eliminazione raddoppia
        # i tie ad ogni round precedente). Se la size effettiva matcha l'attesa, uso
        # il nome canonico. Se invece è uguale alla size del round successivo (caso UCL
        # con KO Playoffs prima dell'R16), uso "Knockout Playoffs".
        canonical = {
            1: ("Final", "Finale"),
            2: ("Semifinals", "Semifinali"),
            4: ("Quarterfinals", "Quarti di finale"),
            8: ("Round of 16", "Ottavi di finale"),
            16: ("Round of 32", "Sedicesimi"),
        }
        n = len(sized_rounds)
        labels = [None] * n

        if n > 0:
            expected = sized_rounds[-1]["size"]
            for idx in range(n - 1, -1, -1):
                actual = sized_rounds[idx]["size"]
                if actual == expected:
                    labels[idx] = canonical.get(actual, (f"Round of {actual*2}", f"{actual*2}-esimi"))
                    expected = actual * 2
                elif idx + 1 < n and actual == sized_rounds[idx + 1]["size"]:
                    # Stessa size del round successivo → playoff/preliminare
                    if actual == 8:
                        labels[idx] = ("Knockout Playoffs", "Spareggi KO")
                    elif actual == 16:
                        labels[idx] = ("Preliminary Round", "Turno preliminare")
                    else:
                        labels[idx] = canonical.get(actual, (f"Round of {actual*2}", f"{actual*2}-esimi"))
                    # non cambio expected: il prossimo round (precedente) dovrebbe essere doppio
                    expected = actual * 2
                else:
                    labels[idx] = canonical.get(actual, (f"Round of {actual*2}", f"{actual*2}-esimi"))
                    expected = actual * 2

        for idx, sr in enumerate(sized_rounds):
            name_en, name_it = labels[idx]
            # team_a/team_b portano un 'id' usato solo internamente per il raggruppamento
            # dei tie: la card non lo legge, lo rimuoviamo dall'output.
            for tie in sr["ties"]:
                tie.get("team_a", {}).pop("id", None)
                tie.get("team_b", {}).pop("id", None)
            out["rounds"].append({
                "name": name_en,
                "name_it": name_it,
                "size": sr["size"],
                "ties": sr["ties"],
            })

        out["ties_count"] = sum(len(sr["ties"]) for sr in sized_rounds)
    except Exception as e:
        _LOGGER.error(f"Errore nel processare bracket: {e}")
    return out
