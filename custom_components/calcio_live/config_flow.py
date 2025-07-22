import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
import logging
import aiohttp
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

OPTION_SELECT_CAMPIONATO = "Campionato"
OPTION_SELECT_TEAM = "Team"
OPTION_MANUAL_TEAM = "Inserimento Manuale ID"
OPTION_ALL_TODAY = "Tutte le partite del giorno"

@config_entries.HANDLERS.register(DOMAIN)
class CalcioLiveConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self._errors = {}
        self._data = {}
        self._teams = []

    async def async_step_user(self, user_input=None):
        self._errors = {}

        if user_input is not None:
            selection = user_input.get("selection")

            if selection == OPTION_SELECT_CAMPIONATO:
                self._data.update(user_input)
                return await self.async_step_campionato()

            elif selection == OPTION_SELECT_TEAM:
                self._data.update(user_input)
                return await self.async_step_select_competition_for_team()
            
            elif selection == OPTION_ALL_TODAY:
                self._data.update(user_input)
                self._data["competition_code"] = "99999"  # Assegna un valore fittizio per creare il sensore
                return self.async_create_entry(
                    title="Tutte le partite di oggi",
                    data=self._data,
                )
            

            elif selection == OPTION_MANUAL_TEAM:
                self._data.update(user_input)
                return await self.async_step_manual_team()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("selection", default=OPTION_SELECT_CAMPIONATO): vol.In([OPTION_SELECT_CAMPIONATO, OPTION_SELECT_TEAM, OPTION_ALL_TODAY, OPTION_MANUAL_TEAM]),
            }),
            errors=self._errors,
            description_placeholders={
                "description": (
                    "Benvenuto nella configurazione di Calcio Live.\n\n"
                    "Seleziona una delle opzioni per creare un sensore:\n\n"
                    "- **Campionato**: per monitorare tutte le partite di un campionato.\n"
                    "- **Squadra**: per monitorare una specifica squadra.\n"
                    "- **Tutte**: per monitorare tutte le partite della giornata (di tutto il mondo).\n"
                    "- **Inserimento Manuale**: se conosci l'ID della squadra specifica."
                )
            }
        )

    async def async_step_campionato(self, user_input=None):
        if user_input is not None:
            competition_code = user_input.get("competition_code")
            competition_name = await self._get_competition_name(competition_code)
            self._data.update({"competition_code": competition_code, "name": competition_name})

            return await self.async_step_dates()

        competitions = await self._get_competitions()
        sorted_competitions = {k: v for k, v in sorted(competitions.items(), key=lambda item: item[1])}

        return self.async_show_form(
            step_id="campionato",
            data_schema=vol.Schema({
                vol.Required("competition_code"): vol.In(sorted_competitions),
            }),
            errors=self._errors,
            description_placeholders={
                "description": (
                    "Scegli il campionato che desideri monitorare.\n"
                    "Verranno mostrati i dati relativi a tutte le squadre del campionato selezionato."
                )
            }
        )

    async def async_step_select_competition_for_team(self, user_input=None):
        if user_input is not None:
            competition_code = user_input.get("competition_code")
            self._data.update({"competition_code": competition_code})

            await self._get_teams(competition_code)
            return await self.async_step_team()

        competitions = await self._get_competitions()
        sorted_competitions = {k: v for k, v in sorted(competitions.items(), key=lambda item: item[1])}

        return self.async_show_form(
            step_id="select_competition_for_team",
            data_schema=vol.Schema({
                vol.Required("competition_code"): vol.In(sorted_competitions),
            }),
            errors=self._errors,
            description_placeholders={
                "description": (
                    "Scegli il campionato per il quale vuoi selezionare una squadra specifica.\n"
                    "Dopo aver scelto il campionato, potrai selezionare una squadra dalla lista."
                )
            }
        )

    async def async_step_team(self, user_input=None):
        if user_input is not None:
            team_name = user_input["team_name"]
            competition_code = self._data.get("competition_code", "N/A")
            competition_name = await self._get_competition_name(competition_code)

            # Trova l'ID della squadra selezionata
            selected_team = next((team for team in self._teams if team["displayName"] == team_name), None)
            team_id = selected_team["id"] if selected_team else None

            # Aggiorna self._data con il team_id
            self._data.update({"team_name": team_name, "team_id": team_id, "name": f"Team {competition_name} {team_name}"})

            return await self.async_step_dates()

        team_options = {team['displayName']: team['displayName'] for team in sorted(self._teams, key=lambda t: t['displayName'])}

        return self.async_show_form(
            step_id="team",
            data_schema=vol.Schema({
                vol.Required("team_name"): vol.In(team_options),
            }),
            errors=self._errors,
            description_placeholders={
                "description": (
                    "Scegli la squadra che desideri monitorare.\n"
                    "Verranno mostrate solo le partite di questa squadra."
                )
            }
        )

    async def async_step_manual_team(self, user_input=None):
        if user_input is not None:
            team_id = user_input["manual_team_id"]
            competition_code = self._data.get("competition_code", "N/A")
            competition_name = await self._get_competition_name(competition_code)
            nome_squadra = user_input.get("name", "Nome Squadra (a piacere)")
            nome_squadra_normalizzato = nome_squadra.replace(" ", "_").lower()

            self._data.update({"team_id": team_id, "name": f"Team {competition_name} {team_id} {nome_squadra_normalizzato}"})

            return await self.async_step_dates()

        return self.async_show_form(
            step_id="manual_team",
            data_schema=vol.Schema({
                vol.Required("manual_team_id"): str,
                vol.Optional("name", default="Nome Squadra (a piacere)"): str,
            }),
            errors=self._errors,
            description_placeholders={
                "description": (
                    "Se conosci l'ID della squadra, puoi inserirlo manualmente.\n"
                    "Puoi anche specificare un nome personalizzato per identificarla facilmente."
                )
            }
        )

    async def async_step_dates(self, user_input=None):
        """Schermata per configurare start_date e end_date."""
        today = datetime.now()

        # Recupero delle date dinamiche tramite il metodo _get_calendar_data
        start_date, end_date = await self._get_calendar_data()

        # Se non vengono trovate date dal calendario, usa valori predefiniti
        if start_date is None or end_date is None:
            start_date = today.strftime("%Y-%m-%d")  # Default: la data di oggi
            end_date = (today + timedelta(days=30)).strftime("%Y-%m-%d")  # Default: 30 giorni da oggi

        # Se l'utente ha fornito input, aggiorniamo i dati
        if user_input is not None:
            self._data.update({
                "start_date": user_input.get("start_date", start_date),
                "end_date": user_input.get("end_date", end_date),
            })
            return self.async_create_entry(
                title=self._data.get("name", "Calcio Live"),
                data=self._data,
            )

        # Mostra il form per l'inserimento delle date con i valori predefiniti
        return self.async_show_form(
            step_id="dates",
            data_schema=vol.Schema({
                vol.Optional("start_date", default=start_date): str,
                vol.Optional("end_date", default=end_date): str,
            }),
            description_placeholders={
                "description": (
                    "Inserisci il periodo di monitoraggio per le partite.\n\n"
                    "- La data di inizio determina da quando iniziare a monitorare.\n"
                    "- La data di fine determina fino a quando monitorare.\n\n"
                    "Entrambe le date devono essere nel formato **YYYY-MM-DD**."
                )
            }
        )
    
    async def _get_calendar_data(self):
        """Recupera il calendario delle partite per ottenere le date di inizio e fine"""
        competition_code = self._data.get("competition_code", "N/A")

        if competition_code == "99999":
            #_LOGGER.warning("Competition code 99999 escluso dal recupero del calendario.")
            return None, None

        calendar_url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{competition_code}/scoreboard"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(calendar_url) as response:
                    response.raise_for_status()
                    data = await response.json()
                    # Estrai le date di inizio e fine dal calendario
                    calendar_start_date = data.get("calendarStartDate", "2025-08-01T04:00Z")
                    calendar_end_date = data.get("calendarEndDate", "2026-07-01T03:59Z")
                    return calendar_start_date[:10], calendar_end_date[:10]
        except Exception as e:
            _LOGGER.error(f"Errore nel recupero del calendario: {e}")
            return None, None
    

    async def _get_competitions(self):
        url = "https://site.api.espn.com/apis/site/v2/leagues/dropdown?lang=en&region=us&calendartype=whitelist&limit=200&sport=soccer"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    response.raise_for_status()
                    competitions_data = await response.json()
                    return {league['slug']: league['name'] for league in competitions_data.get("leagues", [])}
        except aiohttp.ClientError as e:
            _LOGGER.error(f"Errore nel caricamento delle competizioni: {e}")
            return {}

    async def _get_competition_name(self, competition_code):
        """Recupera il nome della competizione dato il suo codice."""
        competitions = await self._get_competitions()
        return competitions.get(competition_code, "Nome Sconosciuto")

    async def _get_teams(self, competition_code):
        url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{competition_code}/teams"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    response.raise_for_status()
                    teams_data = await response.json()
                
                    leagues = teams_data.get("sports", [{}])[0].get("leagues", [{}])
                    if not leagues:
                        self._teams = []
                        return

                    self._teams = [
                        {"id": team["team"]["id"], "displayName": team["team"]["displayName"]}
                        for league in leagues for team in league.get("teams", [])
                    ]
        except aiohttp.ClientError as e:
            _LOGGER.error(f"Errore nel caricamento delle squadre per {competition_code}: {e}")
            self._teams = []

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Gestore per il flusso delle opzioni."""
        return CalcioLiveOptionsFlow(config_entry)


class CalcioLiveOptionsFlow(config_entries.OptionsFlow):

    def __init__(self, config_entry):
        super().__init__()
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        today = datetime.now()

        start_date = self._config_entry.options.get(
            "start_date", self._config_entry.data.get("start_date", (today - relativedelta(months=3)).strftime("%Y-%m-%d"))
        )
        end_date = self._config_entry.options.get(
            "end_date", self._config_entry.data.get("end_date", (today + relativedelta(months=4)).strftime("%Y-%m-%d"))
        )
        

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional("start_date", default=start_date): str,
                vol.Optional("end_date", default=end_date): str,
                vol.Optional("info", default="⚠ Dopo la modifica, riavvia Home Assistant.", description=""): str,
            }),
        )
        
        
