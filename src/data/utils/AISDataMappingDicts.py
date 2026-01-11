Id2AttributeName_Mapping = {
    0: "ship_type", 1: "cargo_type", 2: "width", 3: "length", 4: "draught",
    5: "destination", 6: "navigational_status", 7: "sog", 8: "rot", 9: "cog",
    10: "heading", 11: "latitude", 12: "longitude", 13: "timestamp"
}

ColumnName_Standard_Mapping_US2DK = {
    "LAT": "Latitude",
    "LON": "Longitude",
    "BaseDateTime": "# Timestamp",
    "Status": "Navigational status",
    "Cargo": "Cargo type",
    "Draft": "Draught",
    "VesselType": "Ship type"
}

ColumnName_Standard_Mapping_DK2Standard = {
    "MMSI": "mmsi",
    "# Timestamp": "timestamp",
    "Longitude": "longitude",
    "Latitude": "latitude",
    "Heading": "heading",
    "COG": "cog",
    "ROT": "rot",
    "SOG": "sog",
    "Navigational status": "navigational_status",
    "Cargo type": "cargo_type",
    "Destination": "destination",
    "Draught": "draught",
    "Length": "length",
    "Width": "width",
    "Ship type": "ship_type"
}

Id2NAV_STATUS_Mapping = {
    0: "Under way using engine",
    1: "At anchor",
    2: "Not under command",
    3: "Restricted manoeuverability",
    4: "Constrained by her draught",
    5: "Moored",
    6: "Aground",
    7: "Engaged in Fishing",
    8: "Under way sailing",
    14: "AIS-SART active",
    15: "Not defined"
}
Id2SHIP_TYPE_Mapping = {
    0:  "Not available",
    **{i: "Reserved" for i in range(1, 20)},
    20: "Wing in ground (WIG)",
    21: "WIG category A", 22: "WIG category B", 23: "WIG category C", 24: "WIG category D",
    **{i: "WIG Reserved" for i in range(25, 30)},
    30: "Fishing", 31: "Towing", 32: "Towing (large)", 33: "Dredging or underwater ops",
    34: "Diving ops", 35: "Military ops", 36: "Sailing", 37: "Pleasure Craft", 38: "Reserved", 39: "Reserved",
    40: "High speed craft (HSC)", 41: "HSC Hazardous category A", 42: "HSC Hazardous category B",
    43: "HSC Hazardous category C", 44: "HSC Hazardous category D",
    **{i: "HSC Reserved" for i in range(45, 49)}, 49: "HSC No additional information",
    50: "Pilot Vessel", 51: "Search and Rescue vessel", 52: "Tug", 53: "Port Tender",
    54: "Anti-pollution equipment", 55: "Law Enforcement", 56: "Spare - Local Vessel",
    57: "Spare - Local Vessel", 58: "Medical Transport", 59: "Noncombatant ship",
    60: "Passenger", 61: "Passenger Hazardous category A", 62: "Passenger Hazardous category B",
    63: "Passenger Hazardous category C", 64: "Passenger Hazardous category D",
    **{i: "Passenger Reserved" for i in range(65, 69)}, 69: "Passenger No additional information",
    70: "Cargo", 71: "Cargo Hazardous category A", 72: "Cargo Hazardous category B",
    73: "Cargo Hazardous category C", 74: "Cargo Hazardous category D",
    **{i: "Cargo Reserved" for i in range(75, 79)}, 79: "Cargo No additional information",
    80: "Tanker", 81: "Tanker Hazardous category A", 82: "Tanker Hazardous category B",
    83: "Tanker Hazardous category C", 84: "Tanker Hazardous category D",
    **{i: "Tanker Reserved" for i in range(85, 89)}, 89: "Tanker No additional information",
    90: "Other Type", 91: "Other Type Hazardous category A", 92: "Other Type Hazardous category B",
    93: "Other Type Hazardous category C", 94: "Other Type Hazardous category D",
    **{i: "Other Type Reserved" for i in range(95, 97)},
}