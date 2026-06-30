from __future__ import annotations

from collections.abc import Mapping, Sequence
import re
from typing import Any


ENERGY_OVERVIEW_PATH = "/rest/hems-configurator/energy-overview"
THINGS_PATH = "/rest/hems-configurator/things"
HEMS_THING_PROPERTY = "solarwatt.hemsConfigurator"
ENERGY_OVERVIEW_THING_PROPERTY = "solarwatt.energyOverview"
ENERGY_OVERVIEW_THING_UID = "energy-overview:standard:energy-overview"

_ENERGY_OVERVIEW_ITEM_NAMES = (
    "production",
    "feedIn",
    "feedOut",
    "householdConsumption",
    "storagePowerIn",
    "storagePowerOut",
)
_ENERGY_OVERVIEW_ITEM_NAME_SET = set(_ENERGY_OVERVIEW_ITEM_NAMES)


def energy_overview_to_items(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Convert the HEMS energy overview response to OpenHAB-like items."""
    return [
        _power_item(item_name, item_name, payload.get(item_name), "energy_overview")
        for item_name in _ENERGY_OVERVIEW_ITEM_NAMES
        if item_name in payload
    ]


def energy_overview_to_legacy_items(
    payload: Mapping[str, Any],
    things: Sequence[Any],
) -> list[dict[str, Any]]:
    """Build legacy item names from HEMS overview data for existing entity IDs."""
    items: list[dict[str, Any]] = []
    ids_by_category = _thing_ids_by_category(things)

    if location_id := ids_by_category.get("location"):
        items.extend(_location_legacy_items(location_id, payload))

    if pvplant_id := ids_by_category.get("pvplant"):
        items.extend(_pvplant_legacy_items(pvplant_id, payload))

    if inverter_id := ids_by_category.get("inverter"):
        items.extend(_inverter_legacy_items(inverter_id, payload))

    if meter_id := ids_by_category.get("meter"):
        items.extend(_meter_legacy_items(meter_id, payload))

    if battery_id := ids_by_category.get("battery"):
        items.extend(_battery_legacy_items(battery_id, payload))

    return items


def battery_soc_to_legacy_items(
    things: Sequence[Any],
    soc: int | float,
) -> list[dict[str, Any]]:
    """Build legacy battery SoC item names from an inverter Modbus read."""
    ids_by_category = _thing_ids_by_category(things)
    battery_id = ids_by_category.get("battery")
    if not battery_id:
        return []

    prefix = _item_prefix(battery_id)
    return [
        _battery_item(
            f"{prefix}_battery_bms_soc",
            "Battery BMS SoC",
            soc,
        ),
        _battery_item(
            f"{prefix}_battery_bms_1_soc",
            "Battery BMS 1 SoC",
            soc,
        ),
    ]


def item_names_to_thing_uids(
    item_names: Sequence[Any],
    things: Sequence[Any],
) -> dict[str, str]:
    """Map generated legacy HEMS item names back to their owning things."""
    thing_prefixes: list[tuple[str, str]] = []
    for raw_thing in things:
        if not isinstance(raw_thing, Mapping):
            continue
        thing_uid = str(
            raw_thing.get("UID") or raw_thing.get("uid") or raw_thing.get("id") or ""
        ).strip()
        if not thing_uid:
            continue
        if prefix := _item_prefix(thing_uid):
            thing_prefixes.append((prefix, thing_uid))

    thing_prefixes.sort(key=lambda item: len(item[0]), reverse=True)

    item_to_thing_uid: dict[str, str] = {}
    for raw_item_name in item_names:
        item_name = str(raw_item_name or "").strip()
        if not item_name:
            continue
        if item_name in _ENERGY_OVERVIEW_ITEM_NAME_SET:
            item_to_thing_uid[item_name] = ENERGY_OVERVIEW_THING_UID
            continue
        for prefix, thing_uid in thing_prefixes:
            if item_name == prefix or item_name.startswith(f"{prefix}_"):
                item_to_thing_uid[item_name] = thing_uid
                break

    return item_to_thing_uid


def extended_modbus_to_legacy_items(
    things: Sequence[Any],
    values: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Build legacy-compatible item names for optional read-only Modbus data."""
    ids_by_category = _thing_ids_by_category(things)
    items: list[dict[str, Any]] = []

    def add(
        category: str,
        suffix: str,
        label: str,
        key: str,
        item_type: str,
        unit: str | None = None,
        pattern: str | None = None,
    ) -> None:
        thing_id = ids_by_category.get(category)
        if not thing_id or key not in values:
            return
        items.append(
            _typed_item(
                f"{_item_prefix(thing_id)}_{suffix}",
                label,
                values[key],
                item_type,
                unit,
                pattern,
                "modbus",
            )
        )

    for category, suffix, label in (
        ("inverter", "inverter_work_pv_total", "Inverter PV Energy Total"),
        ("pvplant", "harmonized_work_out_total", "PV Energy Total"),
        ("location", "harmonized_work_produced_total", "PV Energy Total"),
    ):
        add(category, suffix, label, "solar_energy_total", "Number:Energy", "kWh", "%.2f kWh")
    for category, suffix, label in (
        ("inverter", "modbus_solar_energy_today", "Solar Energy Today"),
        ("pvplant", "modbus_solar_energy_today", "Solar Energy Today"),
    ):
        add(category, suffix, label, "solar_energy_today", "Number:Energy", "kWh", "%.2f kWh")

    add("battery", "battery_work_in_total", "Battery Charge Energy Total", "battery_charge_total", "Number:Energy", "kWh", "%.2f kWh")
    add("battery", "modbus_battery_charge_today", "Battery Charge Energy Today", "battery_charge_today", "Number:Energy", "kWh", "%.2f kWh")
    add("battery", "battery_work_out_total", "Battery Discharge Energy Total", "battery_discharge_total", "Number:Energy", "kWh", "%.2f kWh")
    add("battery", "modbus_battery_discharge_today", "Battery Discharge Energy Today", "battery_discharge_today", "Number:Energy", "kWh", "%.2f kWh")

    add("meter", "meter_work_out_total", "Meter Feed-in Energy Total", "feed_in_energy_total", "Number:Energy", "kWh", "%.2f kWh")
    add("meter", "modbus_feed_in_energy_today", "Feed-in Energy Today", "feed_in_energy_today", "Number:Energy", "kWh", "%.2f kWh")
    add("meter", "meter_work_in_total", "Meter Grid Consumption Energy Total", "grid_consumption_energy_total", "Number:Energy", "kWh", "%.2f kWh")
    add("meter", "modbus_grid_consumption_energy_today", "Grid Consumption Energy Today", "grid_consumption_energy_today", "Number:Energy", "kWh", "%.2f kWh")

    add("inverter", "inverter_work_out_total", "Inverter Yield Total", "total_yield_total", "Number:Energy", "kWh", "%.2f kWh")
    add("inverter", "modbus_total_yield_today", "Inverter Yield Today", "total_yield_today", "Number:Energy", "kWh", "%.2f kWh")
    add("inverter", "inverter_work_in_total", "Inverter Input Energy Total", "input_energy_total", "Number:Energy", "kWh", "%.2f kWh")
    add("inverter", "modbus_input_energy_today", "Inverter Input Energy Today", "input_energy_today", "Number:Energy", "kWh", "%.2f kWh")

    add("battery", "battery_bms_1_voltage", "Battery BMS 1 Voltage", "battery_bms_1_voltage", "Number:ElectricPotential", "V", "%.1f V")
    add("battery", "battery_bms_1_current", "Battery BMS 1 Current", "battery_bms_1_current", "Number:ElectricCurrent", "A", "%.1f A")
    add("battery", "battery_bms_1_temperature", "Battery BMS 1 Temperature", "battery_bms_1_temperature", "Number:Temperature", "°C", "%.1f °C")
    add("battery", "battery_bms_1_soh", "Battery BMS 1 SoH", "battery_bms_1_soh", "Number:Dimensionless", "%", "%.0f %%")
    add("battery", "battery_bms_1_kwh_remaining", "Battery BMS 1 kWh Remaining", "battery_bms_1_kwh_remaining", "Number:Energy", "kWh", "%.2f kWh")
    add("battery", "battery_bms_1_cell_temperature_high", "Battery BMS 1 Cell Temperature High", "battery_bms_1_cell_temperature_high", "Number:Temperature", "°C", "%.1f °C")
    add("battery", "battery_bms_1_cell_temperature_low", "Battery BMS 1 Cell Temperature Low", "battery_bms_1_cell_temperature_low", "Number:Temperature", "°C", "%.1f °C")
    add("battery", "battery_bms_1_cell_voltage_high", "Battery BMS 1 Cell Voltage High", "battery_bms_1_cell_voltage_high", "Number:ElectricPotential", "V", "%.2f V")
    add("battery", "battery_bms_1_cell_voltage_low", "Battery BMS 1 Cell Voltage Low", "battery_bms_1_cell_voltage_low", "Number:ElectricPotential", "V", "%.2f V")
    add("battery", "bmsInfo_bms1_status", "BMS 1 Status", "bms_1_status", "String")

    add("inverter", "modbus_inverter_temperature", "Inverter Temperature", "inverter_temperature", "Number:Temperature", "°C", "%.1f °C")
    add("inverter", "modbus_inverter_state_code", "Inverter State Code", "inverter_state_code", "Number")
    add("inverter", "modbus_inverter_fault_1_code", "Inverter Fault 1 Code", "inverter_fault_1_code", "Number")
    add("inverter", "modbus_inverter_fault_2_code", "Inverter Fault 2 Code", "inverter_fault_2_code", "Number")
    add("inverter", "modbus_inverter_fault_3_code", "Inverter Fault 3 Code", "inverter_fault_3_code", "Number")
    add("inverter", "modbus_inverter_faults", "Inverter Faults", "inverter_faults", "String")

    add("battery", "battery_min_soc", "Battery Min SoC", "min_soc", "Number:Dimensionless", "%", "%.0f %%")
    add("battery", "battery_max_soc", "Battery Max SoC", "max_soc", "Number:Dimensionless", "%", "%.0f %%")
    add("battery", "battery_min_soc_on_grid", "Battery Min SoC On Grid", "min_soc_on_grid", "Number:Dimensionless", "%", "%.0f %%")
    add("battery", "battery_battery_maximum_charging_current", "Battery Maximum Charging Current", "max_charge_current", "Number:ElectricCurrent", "A", "%.1f A")
    add("battery", "battery_battery_maximum_discharging_current", "Battery Maximum Discharging Current", "max_discharge_current", "Number:ElectricCurrent", "A", "%.1f A")
    add("inverter", "modbus_work_mode_code", "Work Mode Code", "work_mode_code", "Number")
    add("inverter", "modbus_work_mode", "Work Mode", "work_mode", "String")
    add("inverter", "modbus_import_power_limit", "Import Power Limit", "import_power_limit", "Number:Power", "W", "%.0f W")
    add("inverter", "modbus_export_power_limit", "Export Power Limit", "export_power_limit", "Number:Power", "W", "%.0f W")

    return items


def things_to_openhab_things(payload: Sequence[Any]) -> list[dict[str, Any]]:
    """Convert HEMS thing records to the shape used by existing diagnostics."""
    things: list[dict[str, Any]] = [_energy_overview_thing()]
    for raw_thing in payload:
        if not isinstance(raw_thing, Mapping):
            continue
        uid = str(raw_thing.get("id") or "").strip()
        if not uid:
            continue

        thing_type = raw_thing.get("thingType")
        thing_type = thing_type if isinstance(thing_type, Mapping) else {}
        type_uid = str(thing_type.get("id") or "").strip()
        responsible_bridge = raw_thing.get("responsibleBridge")
        responsible_bridge = (
            responsible_bridge if isinstance(responsible_bridge, Mapping) else {}
        )

        properties = _thing_properties(raw_thing, thing_type)
        properties[HEMS_THING_PROPERTY] = "true"
        thing: dict[str, Any] = {
            "UID": uid,
            "uid": uid,
            "label": raw_thing.get("label") or uid,
            "thingTypeUID": type_uid,
            "thingTypeUid": type_uid,
            "statusInfo": raw_thing.get("statusInfo") or {},
            "properties": properties,
            "channels": [],
        }
        if bridge_uid := str(responsible_bridge.get("id") or "").strip():
            thing["bridgeUID"] = bridge_uid
            thing["bridgeUid"] = bridge_uid
        things.append(thing)
    return things


def is_hems_thing(thing: Mapping[str, Any]) -> bool:
    """Return True for synthetic thing records converted from HEMS configurator data."""
    properties = thing.get("properties")
    props = properties if isinstance(properties, Mapping) else {}
    return str(props.get(HEMS_THING_PROPERTY) or "").strip().lower() == "true"


def is_energy_overview_thing(thing: Mapping[str, Any]) -> bool:
    """Return True for the synthetic Energy Overview device."""
    properties = thing.get("properties")
    props = properties if isinstance(properties, Mapping) else {}
    return str(props.get(ENERGY_OVERVIEW_THING_PROPERTY) or "").strip().lower() == "true"


def _energy_overview_thing() -> dict[str, Any]:
    return {
        "UID": ENERGY_OVERVIEW_THING_UID,
        "uid": ENERGY_OVERVIEW_THING_UID,
        "label": "Energy Overview",
        "thingTypeUID": "energy-overview:standard",
        "thingTypeUid": "energy-overview:standard",
        "statusInfo": {"status": "ONLINE", "statusDetail": "NONE"},
        "properties": {
            HEMS_THING_PROPERTY: "true",
            ENERGY_OVERVIEW_THING_PROPERTY: "true",
            "thingTypeTitle": "Energy Overview",
            "thingTypeCategory": "ENERGY_OVERVIEW",
        },
        "channels": [],
    }


def _power_item(
    name: str,
    label: str,
    value: Any,
    category: str,
) -> dict[str, Any]:
    return {
        "name": name,
        "label": label,
        "state": _power_state(value),
        "type": "Number:Power",
        "editable": False,
        "category": category,
        "stateDescription": {"pattern": "%.0f W"},
    }


def _battery_item(
    name: str,
    label: str,
    value: int | float,
) -> dict[str, Any]:
    return {
        "name": name,
        "label": label,
        "state": _percentage_state(value),
        "type": "Number:Dimensionless",
        "editable": False,
        "category": "energy_overview",
        "stateDescription": {"pattern": "%.0f %%"},
    }


def _typed_item(
    name: str,
    label: str,
    value: Any,
    item_type: str,
    unit: str | None,
    pattern: str | None,
    category: str,
) -> dict[str, Any]:
    item = {
        "name": name,
        "label": label,
        "state": _typed_state(value, unit),
        "type": item_type,
        "editable": False,
        "category": category,
    }
    if pattern:
        item["stateDescription"] = {"pattern": pattern}
    return item


def _legacy_power_items(
    thing_id: str,
    group: str,
    definitions: Sequence[tuple[str, str, Any]],
) -> list[dict[str, Any]]:
    prefix = _item_prefix(thing_id)
    group_prefix = f"{group}_" if group else ""
    return [
        _power_item(
            f"{prefix}_{group_prefix}{suffix}",
            label,
            value,
            "energy_overview",
        )
        for suffix, label, value in definitions
        if value is not None
    ]


def _location_legacy_items(
    thing_id: str,
    payload: Mapping[str, Any],
) -> list[dict[str, Any]]:
    return _legacy_power_items(
        thing_id,
        "harmonized",
        (
            ("power_produced", "Power Produced", payload.get("production")),
            ("power_consumed", "Power Consumed", payload.get("householdConsumption")),
            (
                "power_consumed_from_grid",
                "Power Consumed From Grid",
                payload.get("feedOut"),
            ),
            ("power_out", "Power Out", payload.get("feedIn")),
            ("power_buffered", "Power Buffered", payload.get("storagePowerIn")),
            ("power_released", "Power Released", payload.get("storagePowerOut")),
            (
                "power_consumed_from_storage",
                "Power Consumed From Storage",
                payload.get("storagePowerOut"),
            ),
            (
                "power_out_from_storage",
                "Power Out From Storage",
                payload.get("storagePowerOut"),
            ),
            (
                "power_buffered_from_producers",
                "Power Buffered From Producers",
                payload.get("storagePowerIn"),
            ),
            ("power_self_consumed", "Power Self Consumed", _self_consumed_power(payload)),
        ),
    )


def _pvplant_legacy_items(
    thing_id: str,
    payload: Mapping[str, Any],
) -> list[dict[str, Any]]:
    return _legacy_power_items(
        thing_id,
        "harmonized",
        (("power_out", "Power Out", payload.get("production")),),
    )


def _inverter_legacy_items(
    thing_id: str,
    payload: Mapping[str, Any],
) -> list[dict[str, Any]]:
    return [
        *_legacy_power_items(
            thing_id,
            "",
            (
                (
                    "inverter_total_pv_input_power",
                    "Inverter Total PV Input Power",
                    payload.get("production"),
                ),
                (
                    "electricData_mppt_total_power",
                    "ElectricData MPPT Total Power",
                    payload.get("production"),
                ),
            ),
        ),
        *_legacy_power_items(
            thing_id,
            "harmonized",
            (
                ("mppt_dc_power", "MPPT DC Power", payload.get("production")),
                ("power_out", "Power Out", payload.get("production")),
            ),
        ),
    ]


def _meter_legacy_items(
    thing_id: str,
    payload: Mapping[str, Any],
) -> list[dict[str, Any]]:
    return [
        *_legacy_power_items(
            thing_id,
            "harmonized",
            (
                ("power_in", "Power In", payload.get("feedOut")),
                ("power_out", "Power Out", payload.get("feedIn")),
            ),
        ),
        _power_item(
            f"{_item_prefix(thing_id)}_meter_active_power_total",
            "Meter Active Power Total",
            _net_grid_power(payload),
            "energy_overview",
        ),
    ]


def _battery_legacy_items(
    thing_id: str,
    payload: Mapping[str, Any],
) -> list[dict[str, Any]]:
    net_battery_power = _net_battery_power(payload)
    return [
        *_legacy_power_items(
            thing_id,
            "harmonized",
            (
                ("power_in", "Power In", payload.get("storagePowerIn")),
                ("power_out", "Power Out", payload.get("storagePowerOut")),
            ),
        ),
        *_legacy_power_items(
            thing_id,
            "battery",
            (
                (
                    "battery_calculated_power",
                    "Battery Calculated Power",
                    net_battery_power,
                ),
                ("bms_power", "Battery BMS Power", net_battery_power),
                ("bms_1_power", "Battery BMS 1 Power", net_battery_power),
            ),
        ),
    ]


def _thing_ids_by_category(things: Sequence[Any]) -> dict[str, str]:
    ids: dict[str, str] = {}
    for raw_thing in things:
        if not isinstance(raw_thing, Mapping):
            continue
        thing_id = str(
            raw_thing.get("id") or raw_thing.get("UID") or raw_thing.get("uid") or ""
        ).strip()
        if not thing_id:
            continue
        thing_type = raw_thing.get("thingType")
        thing_type = thing_type if isinstance(thing_type, Mapping) else {}
        type_id = str(
            thing_type.get("id")
            or raw_thing.get("thingTypeUID")
            or raw_thing.get("thingTypeUid")
            or ""
        ).strip().lower()
        category = thing_type.get("category")
        category = category if isinstance(category, Mapping) else {}
        category_type = str(category.get("type") or "").strip().upper()

        if "kiwigrid-location" in type_id:
            ids.setdefault("location", thing_id)
        elif type_id.startswith("pvplant:"):
            ids.setdefault("pvplant", thing_id)
        elif "inverter" in type_id and "bridge" not in type_id:
            ids.setdefault("inverter", thing_id)
        elif "battery" in type_id or category_type == "STORAGES":
            ids.setdefault("battery", thing_id)
        elif "meter" in type_id or category_type == "POWER_METERS":
            ids.setdefault("meter", thing_id)
    return ids


def _item_prefix(thing_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", thing_id).strip("_")


def _power_state(value: Any) -> str:
    if isinstance(value, bool) or value is None:
        return "NULL"
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "NULL"
    if numeric.is_integer():
        return f"{int(numeric)} W"
    return f"{numeric} W"


def _percentage_state(value: int | float) -> str:
    numeric = float(value)
    if numeric.is_integer():
        return f"{int(numeric)} %"
    return f"{numeric} %"


def _typed_state(value: Any, unit: str | None) -> str:
    if isinstance(value, bool) or value is None:
        return "NULL"
    if isinstance(value, (int, float)):
        if not isinstance(value, bool) and float(value).is_integer():
            rendered = str(int(value))
        else:
            rendered = str(value)
        return f"{rendered} {unit}" if unit else rendered
    return str(value)


def _numeric_value(payload: Mapping[str, Any], key: str) -> float | None:
    value = payload.get(key)
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _net_grid_power(payload: Mapping[str, Any]) -> float | None:
    feed_out = _numeric_value(payload, "feedOut")
    feed_in = _numeric_value(payload, "feedIn")
    if feed_out is None and feed_in is None:
        return None
    return (feed_out or 0) - (feed_in or 0)


def _net_battery_power(payload: Mapping[str, Any]) -> float | None:
    storage_out = _numeric_value(payload, "storagePowerOut")
    storage_in = _numeric_value(payload, "storagePowerIn")
    if storage_out is None and storage_in is None:
        return None
    return (storage_out or 0) - (storage_in or 0)


def _self_consumed_power(payload: Mapping[str, Any]) -> float | None:
    production = _numeric_value(payload, "production")
    feed_in = _numeric_value(payload, "feedIn")
    if production is None and feed_in is None:
        return None
    return max((production or 0) - (feed_in or 0), 0)


def _thing_properties(
    raw_thing: Mapping[str, Any],
    thing_type: Mapping[str, Any],
) -> dict[str, str]:
    category = thing_type.get("category")
    category = category if isinstance(category, Mapping) else {}
    properties: dict[str, str] = {}
    for key, value in (
        ("serialNumber", raw_thing.get("serialNumber")),
        ("thingTypeTitle", thing_type.get("title")),
        ("thingTypeCategory", category.get("type")),
    ):
        if text := str(value or "").strip():
            properties[key] = text
    return properties
