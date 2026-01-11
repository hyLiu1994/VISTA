import re

def denmark_ais_data_filter(df):
    required_columns = [
        "# Timestamp", "Longitude", "Latitude", "Heading", "COG", "ROT", "SOG",
        "Navigational status", "Cargo type", "Destination", "Draught", "Length", "Width", "Ship type"
    ]

    df = df.dropna(subset=required_columns)

    for col in required_columns:
        df = df[df[col] != ""]

    numeric_columns = ["Heading", "COG", "ROT", "SOG", "Draught", "Length", "Width"]
    for col in numeric_columns:
        df = df[df[col].apply(lambda x: str(x).replace('.', '', 1).isdigit())]

    df = df[((df['Latitude'] >= -90) & (df['Latitude'] <= 90)) &  ((df['Longitude'] >= -180) & (df['Longitude'] <= 180))]

    invalid_common = ["Unknown", "Unknown value","No additional information", "Reserved for future use",
                     "Reserved for future amendment", "Reserved for future amendment [HSC]", "Undefined"]
    invalid_navigational_status = invalid_common
    df = df[~df["Navigational status"].isin(invalid_navigational_status)]

    invalid_destinations = invalid_common
    invalid_destinations.extend(["#NAME?", "0", "-", ",", "."])
    df = df[~df["Destination"].isin(invalid_destinations)]
    df = df[~df["Destination"].str.startswith("=", na=False)]
    df = df[~df["Destination"].str.startswith("?", na=False)]
    df["Destination"] = df["Destination"].apply(process_destination)
    df = df[df["Destination"].notna()]
    # df = df[~df["Destination"].str.contains(r"[ /]", na=False)]

    invalid_cargo_types = invalid_common
    df = df[~df["Cargo type"].isin(invalid_cargo_types)]

    invalid_ship_types = invalid_common
    df = df[~df["Ship type"].isin(invalid_ship_types)]

    columns_to_keep = [
       "MMSI", "# Timestamp", "Longitude", "Latitude", "Heading", "COG", "ROT", "SOG",
        "Navigational status", "Cargo type", "Destination", "Draught", "Length", "Width", "Ship type"
    ]
    df = df[columns_to_keep]
    df = df[(df['Length'] > 0) & (df['Width'] > 0)]
    df = df[((df['COG'] >= 0) & (df['COG'] <= 360)) & ((df['Heading'] >= 0) & (df['Heading'] <= 360))]
    df = df[df["MMSI"] != 0]
    return df

def american_ais_data_filter(df):
    # Define the required columns that must be present in the dataset
    required_columns = [
        "MMSI", "BaseDateTime", "LON", "LAT", "Heading", "COG", "SOG",
        "Status", "Cargo", "Draft", "Length", "Width", "VesselType"
    ]

    # Drop rows where any of the required columns have missing values
    df = df.dropna(subset=required_columns)

    # Remove rows where any of the required columns contain empty strings
    for col in required_columns:
        df = df[df[col] != ""]

    # Ensure numeric columns only contain valid numeric values
    numeric_columns = ["Heading", "COG", "SOG", "Draft", "Length", "Width"]
    for col in numeric_columns:
        # Check if the value is numeric by removing at most one decimal point
        df = df[df[col].apply(lambda x: str(x).replace('.', '', 1).isdigit())]

    # Filter latitude and longitude to ensure they are within valid ranges
    df = df[((df['LAT'] >= -90) & (df['LAT'] <= 90)) & ((df['LON'] >= -180) & (df['LON'] <= 180))]

    # Filter course over ground (COG) and heading to ensure they are within [0, 360]
    df = df[((df['COG'] >= 0) & (df['COG'] <= 360)) & ((df['Heading'] >= 0) & (df['Heading'] <= 360))]

    # Filter vessel dimensions to ensure length and width are positive
    df = df[(df['Length'] > 0) & (df['Width'] > 0)]

    # Filter cargo type to ensure it is non-negative
    df = df[(df['Cargo'] > 0)]

    # Filter status to ensure it is within [0, 15]
    df = df[(df['Status'] < 15)]

    df = df[df["MMSI"] != 0]

    # Add a new column "ROT" with all values set to -1
    df['ROT'] = -1

    # Add a new column "Destination" with all values set to 1, matching the length of MMSI
    df['Destination'] = 1

    # Specify the columns to keep in the final output
    columns_to_keep = [
        "MMSI", "BaseDateTime", "LON", "LAT", "Heading", "COG", "ROT", "SOG",
        "Status", "Cargo", "Destination", "Draft", "Length", "Width", "VesselType"
    ]
    df = df[columns_to_keep]
    df = df[(df['Length'] > 0) & (df['Width'] > 0)]
    df = df[((df['COG'] >= 0) & (df['COG'] <= 360)) & ((df['Heading'] >= 0) & (df['Heading'] <= 360))]
    df = df[df["MMSI"] != 0]
    # Return the filtered and processed DataFrame
    return df

def process_destination(value):
    value = value.strip().rstrip(".")

    if len(value) == 1 and value.isalpha():
        return None
    if any(char.isdigit() for char in value):
        return None

    if "[" in value and "]" in value:
        match = re.search(r"\[(.*?)\]", value)
        if match:
            return match.group(1).strip().rstrip(".")
    
    if "(" in value and ")" in value:
        match = re.search(r"\((.*?)\)", value)
        if match:
            return match.group(1).strip().rstrip(".")

    via_pattern = r"(.*?)(?:\s+VIA\s+|_VIA_)(.*)"
    via_match = re.search(via_pattern, value, re.IGNORECASE)
    if via_match:
        return via_match.group(1).strip().rstrip("_")

    to_pattern = r"(.*?)(?:\s+TO\s+|_TO_)(.*)"
    to_match = re.search(to_pattern, value, re.IGNORECASE)
    if to_match:
        return to_match.group(2).strip().rstrip("_")

    separators = r"\s*-\s*|\s*<>\s*|\s*>>\s*|\s*>\s*|\s*<->\s*|\s*<-->\s*|\s*->\s*|\s*=>\s*|\s*>=\s*|\s*>=<\s*|\s*<=>\s*|\s*<\s*"
    if not re.search(separators, value):
        return value.strip().rstrip(".")

    parts = re.split(separators, value)
    parts = [part.strip() for part in parts if part.strip().rstrip(".")]
    if parts:
        return parts[-1]

    return value