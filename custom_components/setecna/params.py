"""Modello parametri Setecna → entità HA.

Porting fedele di models/attributes.go dell'addon Ingordigia.
Le trasformazioni jinja dell'addon sono qui tipizzate (div10/mul10/binary/
enum/signed_power) perché controlliamo entrambi i lati in Python.
"""
from __future__ import annotations
from dataclasses import dataclass, field

# enum maps (raw -> label)
ZONE_MODE = {"0": "off", "2": "economy", "3": "comfort",
             "4": "forced off", "6": "forced economy", "23": "forced comfort"}
FORCING = {"0": "automatic", "1": "forced off", "2": "forced economy", "3": "forced comfort"}
FORCING_OPTS = ["automatic", "forced off", "forced economy", "forced comfort"]
FORCING_CMD = {"automatic": "0", "forced off": "1", "forced economy": "2", "forced comfort": "3"}
SEASON = {"0": "winter", "1": "summer"}
CAL_MODE = {"1": "off", "2": "economy", "3": "comfort"}
# forzatura velocità deumidificatore (D{i}_USER_SPEED_CONTROL)
FORCE_SPEED = {"0": "automatica", "1": "bassa", "2": "media", "3": "alta"}
FORCE_SPEED_OPTS = ["automatica", "bassa", "media", "alta"]
FORCE_SPEED_CMD = {"automatica": "0", "bassa": "1", "media": "2", "alta": "3"}


@dataclass
class ParamDef:
    key: str
    name: str
    entity_type: str                       # sensor|binary_sensor|number|select
    device_class: str | None = None
    unit: str | None = None
    state_class: str | None = None
    transform: str | None = None           # div10|mul10|binary|signed_power|enum|timestamp
    options: list[str] | None = None
    enum_map: dict[str, str] | None = None  # raw -> label (display)
    cmd_map: dict[str, str] | None = None   # label -> raw (command)
    min: float | None = None
    max: float | None = None
    step: float | None = None
    zone: int | None = None                # indice zona (per device/climate grouping)


def _temp(key, name, **kw):
    return ParamDef(key, name, "sensor", device_class="temperature", unit="°C",
                    state_class="measurement", transform="div10", **kw)


def _temp_num(key, name, mn, mx, **kw):
    return ParamDef(key, name, "number", device_class="temperature", unit="°C",
                    state_class="measurement", transform="div10", min=mn, max=mx, step=0.1, **kw)


def _binary(key, name, **kw):
    return ParamDef(key, name, "binary_sensor", transform="binary", **kw)


def build_param_map(raw: dict[str, str], read_only: bool = False) -> dict[str, ParamDef]:
    """Costruisce la mappa Id→ParamDef rispecchiando le condizioni dell'addon."""
    m: dict[str, ParamDef] = {}
    w = not read_only  # write abilitato

    def put(p: ParamDef):
        m[p.key] = p

    # --- last update ---
    put(ParamDef("LAST_UPDATE", "Last update", "sensor",
                 device_class="timestamp", transform="timestamp"))

    # --- globals ---
    put(_binary("GLOBAL_ENABLE", "Global state"))
    put(_temp("GLOBAL_T_EXT", "Global external temperature"))
    if w:
        # PATCH 2026-09-03: stagione scrivibile (estate/inverno) — usata dai profili "Fuori casa"
        put(ParamDef("GLOBAL_SEASON", "Global season", "select", transform="enum",
                     enum_map=SEASON, cmd_map={"winter": "0", "summer": "1"}, options=["winter", "summer"]))
    else:
        put(ParamDef("GLOBAL_SEASON", "Global season", "sensor",
                     device_class="enum", transform="enum", enum_map=SEASON))
    put(_binary("GLOBAL_DEICING", "Global de-ice state"))
    put(_temp("GLOBAL_EXPECTED_DEWP", "Global dewpoint"))
    if w:
        put(_temp_num("GLOBAL_ZONE_T_HYST", "Global zone temperature hysteresis", 0.1, 1))
        put(ParamDef("GLOBAL_ZONE_RH_HYST", "Global zone humidity hysteresis", "number",
                     device_class="humidity", unit="%", state_class="measurement",
                     transform="div10", min=1, max=5, step=0.1))
        put(_temp_num("GLOBAL_ZONE_DEICE_TRESH", "Global zone de-ice threshold", 6, 10))
    else:
        put(_temp("GLOBAL_ZONE_T_HYST", "Global zone temperature hysteresis"))
        put(ParamDef("GLOBAL_ZONE_RH_HYST", "Global zone humidity hysteresis", "sensor",
                     device_class="humidity", unit="%", state_class="measurement", transform="div10"))
        put(_temp("GLOBAL_ZONE_DEICE_TRESH", "Global zone de-ice threshold"))

    # --- domestic hot water ---
    put(_binary("ACS_MAIN_OUTPUT", "DHW state"))
    put(_binary("GLOBAL_ACS_ENABLE", "DHW enabled"))
    put(_temp("GLOBAL_T_ACS", "DHW temperature"))
    put(_temp("GLOBAL_SET_ACS", "DHW temperature setpoint"))
    if w:
        put(_temp_num("ACS_SET_ECONOMY", "DHW economy setpoint", 30, 60))
        put(_temp_num("ACS_SET_COMFORT", "DHW comfort setpoint", 30, 60))
        put(_temp_num("ACS_SET_HYST", "DHW setpoint hysteresis", 0, 10))
        put(_temp_num("ACS_SET_DELTA", "DHW second stage deviation", 0, 10))
    else:
        put(_temp("ACS_SET_ECONOMY", "DHW economy setpoint"))
        put(_temp("ACS_SET_COMFORT", "DHW comfort setpoint"))
        put(_temp("ACS_SET_HYST", "DHW setpoint hysteresis"))
        put(_temp("ACS_SET_DELTA", "DHW second stage deviation"))

    # --- analog inputs (1..8) ---
    for i in range(1, 9):
        if raw.get(f"FAIN{i}_TEMP") not in (None, "32769"):
            put(_temp(f"FAIN{i}_TEMP", f"Analog input {i}"))

    # --- digital inputs (1..8) ---
    for i in range(1, 9):
        put(_binary(f"FDIN{i}_STATUS", f"Digital input {i}"))

    # --- digital alarms (1..5) ---
    for i in range(1, 6):
        put(_binary(f"FALDIN{i}_STATUS", f"Alarm {i}"))

    # --- zones (1..32) ---
    for i in range(1, 33):
        if raw.get(f"Z{i}_SENSOR_CHN", "0") == "0":
            continue
        put(_binary(f"Z{i}_OUTPUT", f"Zone {i} state", zone=i))
        put(_temp(f"Z{i}_TEMP", f"Zone {i} temperature", zone=i))
        # Z{i}_ZONE_MODE non esposto: i codici reali (8/130/146…) sono bitfield
        # non mappabili nell'enum e il climate mostra già modo/azione/preset.
        put(_temp(f"Z{i}_ZONE_SET", f"Zone {i} setpoint", zone=i))
        if w:
            put(ParamDef(f"Z{i}_FORCING", f"Zone {i} preset", "select", transform="enum",
                         enum_map=FORCING, cmd_map=FORCING_CMD, options=FORCING_OPTS, zone=i))
            put(_temp_num(f"Z{i}_SET_CW", f"Zone {i} C.W. setpoint", 15, 30, zone=i))
            put(_temp_num(f"Z{i}_SET_EW", f"Zone {i} E.W. setpoint", 15, 30, zone=i))
            put(_temp_num(f"Z{i}_SET_CS", f"Zone {i} C.S. setpoint", 15, 30, zone=i))
            put(_temp_num(f"Z{i}_SET_ES", f"Zone {i} E.S. setpoint", 15, 30, zone=i))
        else:
            put(ParamDef(f"Z{i}_FORCING", f"Zone {i} preset", "sensor",
                         device_class="enum", transform="enum", enum_map=FORCING, zone=i))
            put(_temp(f"Z{i}_SET_CW", f"Zone {i} C.W. setpoint", zone=i))
            put(_temp(f"Z{i}_SET_EW", f"Zone {i} E.W. setpoint", zone=i))
            put(_temp(f"Z{i}_SET_CS", f"Zone {i} C.S. setpoint", zone=i))
            put(_temp(f"Z{i}_SET_ES", f"Zone {i} E.S. setpoint", zone=i))
        if raw.get(f"Z{i}_RH") not in (None, "32769"):
            put(ParamDef(f"Z{i}_RH", f"Zone {i} humidity", "sensor", device_class="humidity",
                         unit="%", state_class="measurement", transform="div10", zone=i))
            if w:
                put(ParamDef(f"Z{i}_SET_RH", f"Zone {i} humidity setpoint", "number",
                             device_class="humidity", unit="%", state_class="measurement",
                             transform="div10", min=40, max=70, step=0.1, zone=i))
            else:
                put(ParamDef(f"Z{i}_SET_RH", f"Zone {i} humidity setpoint", "sensor",
                             device_class="humidity", unit="%", state_class="measurement",
                             transform="div10", zone=i))

    # --- circuits (1..8) ---
    for i in range(1, 9):
        if raw.get(f"C{i}_TEMP") not in (None, "32769"):
            put(_temp(f"C{i}_TEMP", f"Circuit {i} temperature"))
            put(_temp(f"C{i}_SET", f"Circuit {i} temperature setpoint"))

    # --- sources (1..3) ---
    for i in range(1, 4):
        if raw.get(f"S{i}_DESCR", "0") != "0":
            put(_binary(f"S{i}_ENABLED", f"Source {i} enabled"))
            put(_binary(f"S{i}_OUTPUT", f"Source {i} state"))
            put(_binary(f"S{i}_AUXOUTPUT", f"Source {i} auxiliary state"))

    # --- deumidificatori (1..8): presenti se OUTPUT_DEUM != 255 ---
    # (l'addon li filtrava su SPEED_LOW/ECONOMY != 0, sbagliato per i tipi on/off)
    dehum_name = {1: "Deumidificatore Dependance",
                  2: "Deumidificatore Soggiorno",
                  3: "Deumidificatore Camere"}
    fan_speeds = {"LOW": "low", "MED": "medium", "HIGH": "high",
                  "BOOST": "boost", "ECONOMY": "economy", "COMFORT": "comfort"}
    for i in range(1, 9):
        if raw.get(f"D{i}_OUTPUT_DEUM", "255") == "255":
            continue
        nm = dehum_name.get(i, f"Dehumidifier {i}")
        put(_binary(f"D{i}_OUTPUT_DEUM", f"{nm} deumidificazione"))
        put(_binary(f"D{i}_OUTPUT_RENEW", f"{nm} rinnovo aria"))
        put(_binary(f"D{i}_OUTPUT_VALV", f"{nm} valvola acqua"))
        put(_binary(f"D{i}_OUTPUT_INTG", f"{nm} integrazione"))
        put(ParamDef(f"D{i}_REQ", f"{nm} richiesta", "sensor", state_class="measurement"))
        # forzatura velocità (Automatica/Bassa/Media/Alta) — scrivibile
        if w:
            put(ParamDef(f"D{i}_USER_SPEED_CONTROL", f"{nm} forzatura velocità", "select",
                         transform="enum", enum_map=FORCE_SPEED, cmd_map=FORCE_SPEED_CMD,
                         options=FORCE_SPEED_OPTS))
        else:
            put(ParamDef(f"D{i}_USER_SPEED_CONTROL", f"{nm} forzatura velocità", "sensor",
                         device_class="enum", transform="enum", enum_map=FORCE_SPEED))
        # portate (m³/h) solo se realmente configurate (0/254/255 = non usate)
        for code, lbl in fan_speeds.items():
            key = f"D{i}_SPEED_{code}"
            if raw.get(key, "0") not in ("0", "254", "255"):
                # NB: sono PERCENTUALI di velocità ventilatore (50/70/100), non m³/h.
                # La MTIO0300 fa 280/330/380 m³/h reali (Vel3/Vel2/Vel1 a 20 Pa): il vecchio
                # mul10 + "m³/h" mostrava 500/700/1000, valori inesistenti.
                if w:
                    put(ParamDef(key, f"{nm} velocità {lbl}", "number", unit="%",
                                 state_class="measurement", min=0, max=100, step=5))
                else:
                    put(ParamDef(key, f"{nm} velocità {lbl}", "sensor", unit="%",
                                 state_class="measurement"))

    # --- energy meters (1..4) --- (solo se configurati: DESCR != 0)
    for i in range(1, 5):
        if raw.get(f"EM{i}_DESCR", "0") == "0":
            continue
        put(ParamDef(f"EM{i}_INSTANT", f"Energy meter {i} power", "sensor",
                     device_class="power", unit="kW", state_class="measurement", transform="signed_power"))
        put(ParamDef(f"EM{i}_ACCLO", f"Energy meter {i} total energy import", "sensor",
                     device_class="energy", unit="kWh", state_class="total_increasing", transform="div10"))
        if i == 4:
            put(ParamDef(f"EM{i}_ACC2LO", f"Energy meter {i} total energy export", "sensor",
                         device_class="energy", unit="kWh", state_class="total_increasing", transform="div10"))

    # --- calendars (1..8) ---
    for i in range(1, 9):
        if raw.get(f"MT{i}_XREF", "0") == "0":
            continue
        put(ParamDef(f"MT{i}_MODE", f"Calendar {i} mode", "sensor",
                     device_class="enum", transform="enum", enum_map=CAL_MODE))
        if w:
            put(ParamDef(f"MT{i}_FORCING", f"Calendar {i} preset", "select", transform="enum",
                         enum_map=FORCING, cmd_map=FORCING_CMD, options=FORCING_OPTS))
        else:
            put(ParamDef(f"MT{i}_FORCING", f"Calendar {i} preset", "sensor",
                         device_class="enum", transform="enum", enum_map=FORCING))

    return m


def display_value(p: ParamDef, raw: str):
    """Trasforma il valore grezzo nel valore mostrato/usato da HA."""
    if raw is None or raw == "":
        return None
    t = p.transform
    # 32769 (0x8001) = sensore assente/non collegato → non disponibile
    if t in ("div10", "mul10", "signed_power") and raw == "32769":
        return None
    try:
        if t == "div10":
            return round(int(raw) / 10, 1)
        if t == "mul10":
            return int(raw) * 10
        if t == "binary":
            return raw == "1"
        if t == "enum":
            return p.enum_map.get(raw, raw)
        if t == "signed_power":
            v = int(raw)
            return round((v - 65536) / 100 if v >= 32768 else v / 100, 2)
        if t == "timestamp":
            return raw  # già ISO dal coordinator
    except (ValueError, TypeError):
        return None
    return raw


def command_value(p: ParamDef, value) -> str:
    """Trasforma il valore HA nel valore grezzo da inviare (putmprop)."""
    t = p.transform
    if p.entity_type == "select" and p.cmd_map:
        return p.cmd_map.get(value, "0")
    if t == "div10":
        return str(int(round(float(value) * 10)))
    if t == "mul10":
        return str(int(float(value) / 10))
    return str(value)
