import sys
import os
root_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(root_path)

import math
import pandas as pd
import requests
from collections import Counter
from typing import Dict, Any, Optional, Union

# cache for API results to avoid redundant calls
_geocode_cache = {}
_lane_cache = {}


def reverse_geocode(lat, lon):
    """
    Reverse geocoding to get geographic location names

    Args:
        lat: latitude
        lon: longitude

    Returns:
        str: Geographic Location Name
    """
    key = (lat, lon)
    if key in _geocode_cache:
        return _geocode_cache[key]
    try:
        url = "https://nominatim.openstreetmap.org/reverse"
        params = {"lat": lat, "lon": lon, "format": "json", "zoom": 10, "addressdetails": 1}
        headers = {"User-Agent": "AIS-Imputation-Script", "Accept-Language": "en"}
        response = requests.get(url, params=params, headers=headers, timeout=15)
        name = response.json().get("display_name", "") if response.status_code == 200 else ""
    except Exception:
        name = ""
    _geocode_cache[key] = name
    return name


def get_shipping_lanes_osm(lat, lon):
    """
    Get information about nearby shipping lanes

    Args:
        lat: latitude
        lon: longitude

    Returns:
        list: Channel name list
    """
    key = (lat, lon)
    if key in _lane_cache:
        return _lane_cache[key]
    try:
        query = f"""
[out:json];
way(around:10000,{lat},{lon})["seamark:type"];
out tags;
""".strip()
        r = requests.post("https://overpass-api.de/api/interpreter", data={"data": query}, timeout=30)
        if r.status_code == 200:
            data = r.json()
            lanes = list(set(el['tags'].get('name', 'Unnamed lane') for el in data.get('elements', []))) or ["Unnamed traffic separation scheme"]
        else:
            lanes = [f"Query failed with status {r.status_code}"]
    except Exception:
        lanes = []
    _lane_cache[key] = lanes
    return lanes


def discretize_bucket(value: Union[float, int, str], step: int, upper: int, unit: str = " m") -> str:
    """
    discretizing continuous numerical values into intervals

    Args:
        value: the value to be discretized
        step: interval step size
        upper: upper limit value
        unit: unit

    Returns:
        str: discretized interval string, such as "[10, 20) m"
    """
    try:
        v = float(value)
    except Exception:
        return "unknown"
    if math.isnan(v):
        return "unknown"
    if v >= upper:
        return f"[{int(upper)}, +∞){unit}"
    low = step * math.floor(v / step)
    high = low + step
    low_s = str(int(low)) if abs(low - int(low)) < 1e-9 else f"{low:g}"
    high_s = str(int(high)) if abs(high - int(high)) < 1e-9 else f"{high:g}"
    return f"[{low_s}, {high_s}){unit}"

def generate_vs(df: pd.DataFrame, 
                            mmsi: int, 
                            sequence_id: Optional[Union[int, str]] = None,
                            block: int = 0) -> Dict[str, Any]:
    """
    Extract all seven static attributes from the DataFrame and create a complete attribute entry

    Args:
        df: DataFrame containing AIS data (data mapped)
        MMSI: Ship MMSI
        sequence _ ID: sequence ID
        block: block number (position of the current segment in the track)

    Returns:
        Dict [str, Any]: Full entry with all static attributes
    """
    # 1. navigation_status - extract the most common value
    if 'navigational_status' in df.columns:
        nav_values = df['navigational_status'].dropna().tolist()
        navigation_status = Counter(nav_values).most_common(1)[0][0] if nav_values else "unknown"
    else:
        navigation_status = "unknown"
    
    # 2. hazardous_cargo - dangerous goods (if the most common cargo type contains "Hazardous", then "yes", otherwise "no")
    if 'cargo_type' in df.columns:
        cargo_values = df['cargo_type'].dropna().tolist()
        most_common_cargo = Counter(cargo_values).most_common(1)[0][0] if cargo_values else "unknown"
        hazardous_cargo = "yes" if "Hazardous" in most_common_cargo else "no"
    else:
        hazardous_cargo = "unknown"
    
    # 3. vessel_type - ship type (extract the most common value)
    if 'ship_type' in df.columns:
        vessel_values = df['ship_type'].dropna().tolist()
        vessel_type = Counter(vessel_values).most_common(1)[0][0] if vessel_values else "unknown"
    else:
        vessel_type = "unknown"
    
    # 4. spatial_context - spatial context (use the first valid position to query)
    spatial_context = "unknown"
    if 'latitude' in df.columns and 'longitude' in df.columns:
        try:
            lat_lon_data = df[['latitude', 'longitude']].dropna()
            if not lat_lon_data.empty:
                # Get the first valid position
                first_lat = lat_lon_data.iloc[0]['latitude']
                first_lon = lat_lon_data.iloc[0]['longitude']
                
                # Priority 1: Read location name from DataFrame's location_name column
                location_name = ""
                if 'location_name' in df.columns:
                    location_values = df['location_name'].dropna().tolist()
                    if location_values:
                        location_name = location_values[0]  # Use first valid location name
                
                # Fallback: Call API if DataFrame doesn't have location information
                if not location_name:
                    location_name = reverse_geocode(first_lat, first_lon)
                
                # Priority 1: Read shipping lanes from DataFrame's shipping_lanes column
                shipping_lanes = []
                if 'shipping_lanes' in df.columns:
                    lane_values = df['shipping_lanes'].dropna().tolist()
                    if lane_values:
                        # Process shipping lanes information (may be string, need to parse)
                        lanes_str = lane_values[0]
                        if isinstance(lanes_str, str) and lanes_str:
                            # Convert comma-separated string to list to match API return type
                            shipping_lanes = [lane.strip() for lane in lanes_str.split(',')]
                        elif isinstance(lanes_str, list):
                            # If it's already a list, use it directly
                            shipping_lanes = lanes_str
                
                # Fallback: Call API if DataFrame doesn't have shipping lanes information
                if not shipping_lanes:
                    shipping_lanes = get_shipping_lanes_osm(first_lat, first_lon)
                
                # Construct spatial context string
                context_parts = []
                if location_name:
                    context_parts.append(f"location: {location_name}")
                if shipping_lanes:
                    lanes_str = ", ".join(shipping_lanes)
                    context_parts.append(f"nearby_shipping_lanes: {lanes_str}")
                
                spatial_context = "; ".join(context_parts) if context_parts else "unknown"
        except Exception:
            spatial_context = "unknown"
    
    # 5. draught - calculate the median and discretize
    if 'draught' in df.columns:
        try:
            draught_vals = pd.to_numeric(df['draught'], errors='coerce').dropna()
            if not draught_vals.empty:
                draught_med = draught_vals.median()
                draught = discretize_bucket(draught_med, step=2, upper=12, unit=" m")
            else:
                draught = "unknown"
        except Exception:
            draught = "unknown"
    else:
        draught = "unknown"
    
    # 6. length - Calculate the median and discretize
    if 'length' in df.columns:
        try:
            length_vals = pd.to_numeric(df['length'], errors='coerce').dropna()
            if not length_vals.empty:
                length_med = length_vals.median()
                length = discretize_bucket(length_med, step=50, upper=300, unit=" m")
            else:
                length = "unknown"
        except Exception:
            length = "unknown"
    else:
        length = "unknown"
    
    # 7. width - Calculate the median and discretize
    if 'width' in df.columns:
        try:
            width_vals = pd.to_numeric(df['width'], errors='coerce').dropna()
            if not width_vals.empty:
                width_med = width_vals.median()
                width = discretize_bucket(width_med, step=5, upper=30, unit=" m")
            else:
                width = "unknown"
        except Exception:
            width = "unknown"
    else:
        width = "unknown"
    
    # Build a complete attribute entry 
    entry = {
        "MMSI": mmsi,
        "seq": str(sequence_id) if sequence_id is not None else "unknown", 
        "block": block,  
        "navigation_status": navigation_status,
        "hazardous_cargo": hazardous_cargo,
        "vessel_type": vessel_type,
        "spatial_context": spatial_context,
        "draught": draught,
        "length": length,
        "width": width
    }

    return entry

if __name__ == "__main__":
    print(sys.path)
    from src.modules.M0_SDKG import SDKG
    from src.utils.HyperParameters import configure_parser
    parser = configure_parser()
    args = parser.parse_args()
    SDKG = SDKG(args)
    args.raw_data_file = "/mnt/vdb1/2_workspace/interpretable_imputation/data/RawData/aisdk-2024-03-01@31_1.csv"
    from src.data.AISDataProcess import get_training_test_data
    _ , (test_df, mark_missing_test) = get_training_test_data(args)
    segment_idx = 0
    minimal_seg = test_df.iloc[segment_idx * args.mini_segment_len:(segment_idx + 1) * args.mini_segment_len]
    v_s = generate_vs(args, minimal_seg, SDKG)
    print(v_s)