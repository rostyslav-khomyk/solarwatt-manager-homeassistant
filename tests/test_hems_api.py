from __future__ import annotations

from .module_loader import load_component_module

hems_api = load_component_module("hems_api")
energy_overview_to_items = hems_api.energy_overview_to_items
energy_overview_to_legacy_items = hems_api.energy_overview_to_legacy_items
is_energy_overview_thing = hems_api.is_energy_overview_thing
is_hems_thing = hems_api.is_hems_thing
item_names_to_thing_uids = hems_api.item_names_to_thing_uids
battery_soc_to_legacy_items = hems_api.battery_soc_to_legacy_items
extended_modbus_to_legacy_items = hems_api.extended_modbus_to_legacy_items
things_to_openhab_things = hems_api.things_to_openhab_things


def test_energy_overview_to_items_builds_power_items():
    items = energy_overview_to_items(
        {
            "production": 730,
            "feedIn": 501,
            "feedOut": 0,
            "householdConsumption": 229,
            "storagePowerIn": 0,
            "storagePowerOut": 0,
        }
    )

    assert [item["name"] for item in items] == [
        "production",
        "feedIn",
        "feedOut",
        "householdConsumption",
        "storagePowerIn",
        "storagePowerOut",
    ]
    assert [item["state"] for item in items] == [
        "730 W",
        "501 W",
        "0 W",
        "229 W",
        "0 W",
        "0 W",
    ]
    assert all(item["type"] == "Number:Power" for item in items)


def test_energy_overview_to_legacy_items_builds_existing_power_names():
    items = energy_overview_to_legacy_items(
        {
            "production": 730,
            "feedIn": 501,
            "feedOut": 0,
            "householdConsumption": 229,
            "storagePowerIn": 0,
            "storagePowerOut": 0,
        },
        [
            {
                "id": "kiwigrid-location:standard:location-id",
                "thingType": {"id": "kiwigrid-location:standard"},
            },
            {
                "id": "foxesshybrid:battery:serial",
                "thingType": {
                    "id": "foxesshybrid:battery",
                    "category": {"type": "STORAGES"},
                },
            },
        ],
    )

    states = {item["name"]: item["state"] for item in items}
    assert states["kiwigrid_location_standard_location_id_harmonized_power_produced"] == "730 W"
    assert states["kiwigrid_location_standard_location_id_harmonized_power_out"] == "501 W"
    assert states["kiwigrid_location_standard_location_id_harmonized_power_consumed"] == "229 W"
    assert states["foxesshybrid_battery_serial_harmonized_power_in"] == "0 W"
    assert states["foxesshybrid_battery_serial_harmonized_power_out"] == "0 W"


def test_battery_soc_to_legacy_items_builds_existing_soc_names():
    items = battery_soc_to_legacy_items(
        [
            {
                "id": "foxesshybrid:battery:serial",
                "thingType": {
                    "id": "foxesshybrid:battery",
                    "category": {"type": "STORAGES"},
                },
            },
        ],
        55,
    )

    states = {item["name"]: item for item in items}
    assert states["foxesshybrid_battery_serial_battery_bms_soc"]["state"] == "55 %"
    assert states["foxesshybrid_battery_serial_battery_bms_1_soc"]["state"] == "55 %"


def test_extended_modbus_to_legacy_items_restores_energy_and_bms_names():
    items = extended_modbus_to_legacy_items(
        [
            {
                "id": "kiwigrid-location:standard:location-id",
                "thingType": {"id": "kiwigrid-location:standard"},
            },
            {
                "id": "pvplant:standard:pv-id",
                "thingType": {"id": "pvplant:standard"},
            },
            {
                "id": "foxesshybrid:inverter:serial",
                "thingType": {"id": "foxesshybrid:inverter"},
            },
            {
                "id": "foxesshybrid:meter:serial",
                "thingType": {
                    "id": "foxesshybrid:meter",
                    "category": {"type": "POWER_METERS"},
                },
            },
            {
                "id": "foxesshybrid:battery:serial",
                "thingType": {
                    "id": "foxesshybrid:battery",
                    "category": {"type": "STORAGES"},
                },
            },
        ],
        {
            "solar_energy_total": 346.4,
            "battery_charge_total": 144.4,
            "battery_discharge_total": 139.3,
            "feed_in_energy_total": 2.4,
            "grid_consumption_energy_total": 103.3,
            "battery_bms_1_voltage": 356.3,
            "battery_bms_1_temperature": 33.8,
            "battery_bms_1_soh": 100,
            "bms_1_status": "ONLINE",
            "work_mode": "Self Use",
        },
    )

    states = {item["name"]: item for item in items}
    assert states["foxesshybrid_inverter_serial_inverter_work_pv_total"]["state"] == "346.4 kWh"
    assert states["pvplant_standard_pv_id_harmonized_work_out_total"]["state"] == "346.4 kWh"
    assert states["foxesshybrid_battery_serial_battery_work_in_total"]["state"] == "144.4 kWh"
    assert states["foxesshybrid_battery_serial_battery_work_out_total"]["state"] == "139.3 kWh"
    assert states["foxesshybrid_meter_serial_meter_work_out_total"]["state"] == "2.4 kWh"
    assert states["foxesshybrid_meter_serial_meter_work_in_total"]["state"] == "103.3 kWh"
    assert states["foxesshybrid_battery_serial_battery_bms_1_voltage"]["type"] == "Number:ElectricPotential"
    assert states["foxesshybrid_battery_serial_bmsInfo_bms1_status"]["state"] == "ONLINE"
    assert states["foxesshybrid_inverter_serial_modbus_work_mode"]["state"] == "Self Use"


def test_things_to_openhab_things_preserves_diagnostics_metadata():
    things = things_to_openhab_things(
        [
            {
                "id": "foxesshybrid:battery:123",
                "label": "Vision Battery",
                "thingType": {
                    "id": "foxesshybrid:battery",
                    "title": "Vision Battery",
                    "category": {"type": "STORAGES"},
                },
                "statusInfo": {"status": "ONLINE", "statusDetail": "NONE"},
                "serialNumber": "123",
                "responsibleBridge": {"id": "foxesshybrid:bridge:123"},
            },
            {"label": "Missing id"},
        ]
    )

    assert things == [
        {
            "UID": "energy-overview:standard:energy-overview",
            "uid": "energy-overview:standard:energy-overview",
            "label": "Energy Overview",
            "thingTypeUID": "energy-overview:standard",
            "thingTypeUid": "energy-overview:standard",
            "statusInfo": {"status": "ONLINE", "statusDetail": "NONE"},
            "properties": {
                "solarwatt.hemsConfigurator": "true",
                "solarwatt.energyOverview": "true",
                "thingTypeTitle": "Energy Overview",
                "thingTypeCategory": "ENERGY_OVERVIEW",
            },
            "channels": [],
        },
        {
            "UID": "foxesshybrid:battery:123",
            "uid": "foxesshybrid:battery:123",
            "label": "Vision Battery",
            "thingTypeUID": "foxesshybrid:battery",
            "thingTypeUid": "foxesshybrid:battery",
            "statusInfo": {"status": "ONLINE", "statusDetail": "NONE"},
            "properties": {
                "serialNumber": "123",
                "thingTypeTitle": "Vision Battery",
                "thingTypeCategory": "STORAGES",
                "solarwatt.hemsConfigurator": "true",
            },
            "channels": [],
            "bridgeUID": "foxesshybrid:bridge:123",
            "bridgeUid": "foxesshybrid:bridge:123",
        }
    ]
    assert is_hems_thing(things[0])
    assert is_energy_overview_thing(things[0])
    assert is_hems_thing(things[1])


def test_item_names_to_thing_uids_maps_legacy_hems_items_by_prefix():
    item_to_thing_uid = item_names_to_thing_uids(
        [
            "production",
            "feedIn",
            "kiwigrid_location_standard_location_id_harmonized_power_consumed",
            "foxesshybrid_battery_serial_harmonized_power_out",
            "unknown_prefix_power",
        ],
        [
            {"UID": "energy-overview:standard:energy-overview"},
            {"UID": "kiwigrid-location:standard:location-id"},
            {"UID": "foxesshybrid:battery:serial"},
        ],
    )

    assert item_to_thing_uid == {
        "production": "energy-overview:standard:energy-overview",
        "feedIn": "energy-overview:standard:energy-overview",
        "kiwigrid_location_standard_location_id_harmonized_power_consumed": (
            "kiwigrid-location:standard:location-id"
        ),
        "foxesshybrid_battery_serial_harmonized_power_out": (
            "foxesshybrid:battery:serial"
        ),
    }
