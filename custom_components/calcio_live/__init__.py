from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, _LOGGER

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Scarica la config entry e libera lo slot del sensore 'mixed' condiviso.

    Prima di questo fix mancava del tutto async_unload_entry: senza di esso
    HA considera l'integrazione "supports_unload = False", quindi rimuovere
    un'entry non fa un vero unload ma solo una pulizia del registro, e il
    nome del sensore "mixed" (tracciato in
    hass.data[DOMAIN]["mixed_sensors_created"]) restava occupato fino al
    riavvio di HA anche se l'entry che lo possedeva non esisteva più —
    impedendo a un'altra entry per la stessa squadra di ricrearlo.

    mixed_sensors_created è un dict {mixed_name: owning_entry_id} (vedi
    sensor.py): liberiamo solo i nomi effettivamente posseduti da QUESTA
    entry, non tutti, per non rompere altre entry attive per la stessa
    squadra.
    """
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor"])

    if unload_ok:
        domain_data = hass.data.get(DOMAIN)
        if domain_data:
            mixed_created = domain_data.get("mixed_sensors_created", {})
            stale_names = [
                name for name, owner_id in mixed_created.items()
                if owner_id == entry.entry_id
            ]
            for name in stale_names:
                mixed_created.pop(name, None)
            if stale_names:
                _LOGGER.debug(
                    f"Liberati sensori 'mixed' di proprietà dell'entry {entry.entry_id}: {stale_names}"
                )

    return unload_ok
