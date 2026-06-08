# Setecna REG — Home Assistant integration

Integrazione **custom** (HACS) per i sistemi di termoregolazione **Setecna REG**
tramite il portale cloud `s5a.eu`. **Nessun MQTT, nessun add-on**: l'integrazione
fa login al portale, mantiene la sessione (re-login automatico quando scade) e
crea le entità native HA.

Nasce per sostituire l'add-on `homeassistant-addon-setecna` (Ingordigia), che
perde la connessione MQTT e smette di aggiornare i dati: qui il polling è gestito
da un `DataUpdateCoordinator` che si ri-autentica da solo.

## Entità
- **climate** — un termostato per zona (temperatura, banda comfort/economy
  stagionale, preset *forced off/economy/comfort*, umidità se presente).
- **sensor** — temperature, setpoint, stagione, dewpoint, contatori energia,
  portate ventilazione, ultimo aggiornamento, ecc.
- **binary_sensor** — stati zona/sorgenti/ingressi digitali/allarmi.
- **number** — setpoint scrivibili (zone, ACS, ventilazione, isteresi globali).
- **select** — forzature zona/calendario.

I parametri esposti rispecchiano il modello dell'add-on originale (zone 1-32,
ACS, sorgenti, deumidificatori, contatori energia, calendari, ingressi).

## Installazione
1. HACS → repository custom → questo repo (categoria *Integration*).
2. Riavvia HA.
3. *Impostazioni → Dispositivi e servizi → Aggiungi → Setecna REG*.
4. Inserisci **ID sistema**, **email** e **password** del portale s5a.eu.

## Note
- Valore grezzo `32769` = sensore non collegato → entità *non disponibile*.
- `readonly`: per default i setpoint sono scrivibili; il portale Setecna accetta
  i comandi via `putmprop`.
