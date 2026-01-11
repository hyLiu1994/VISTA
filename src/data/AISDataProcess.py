from src.data.utils.AISDataMappingDicts import Id2AttributeName_Mapping, ColumnName_Standard_Mapping_US2DK, ColumnName_Standard_Mapping_DK2Standard, Id2SHIP_TYPE_Mapping, Id2NAV_STATUS_Mapping
from src.modules.M1_StaticSpatialEncoder import reverse_geocode,get_shipping_lanes_osm
import pandas as pd
import numpy as np
import os
import logging
def get_standardized_data_with_SequenceId(args):
    raw_data_file = args.raw_data_file
    #standardized_data_file = raw_data_file.replace(".csv", "_standardized_with_SequenceId_" + str(args.trajectory_len)+".csv").replace("RawData", "ProcessedData")
    standardized_data_file = raw_data_file.replace(".csv", "_standardized_with_SequenceId_SegementId_PointInfo_" + str(args.trajectory_len)+".csv").replace("CleanedFilteredData", "ProcessedData")
    logging.info(f"standardized_data_file:{standardized_data_file}")
    if os.path.exists(standardized_data_file):
        print("Load standardized data with SequenceId from file:", standardized_data_file)
        df = pd.read_csv(standardized_data_file)
        return df

    print("Get standardized data with SequenceId!")
    df = pd.read_csv(raw_data_file)
    # Step 1: Standardize Data Format
    print("Step 1: Standardize Data Format")
    df.rename(columns=ColumnName_Standard_Mapping_US2DK, inplace=True)
    df.rename(columns=ColumnName_Standard_Mapping_DK2Standard, inplace=True)

    if "timestamp" in df.columns:
        try:
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        except Exception as e:
            print(f"⚠️ Timestamp parsing failed: {e}")

    def apply_map(col: str, mapping: dict):
        if col in df.columns:
            try:
                df[col] = pd.to_numeric(df[col])
            except Exception:
                pass
            try:
                if pd.api.types.is_numeric_dtype(df[col]):
                    df[col] = df[col].map(mapping)
            except Exception as e:
                print(f"⚠️ Column {col} mapping failed: {e}")
        return df

    df = apply_map("navigational_status", Id2NAV_STATUS_Mapping)
    df = apply_map("ship_type", Id2SHIP_TYPE_Mapping)
    df = apply_map("cargo_type", Id2SHIP_TYPE_Mapping)

    if "destination" in df.columns:
        def clean_dest(v):
            if pd.isna(v): return v
            return str(v).strip().upper()
        df["destination"] = df["destination"].apply(clean_dest)

    if {"latitude", "longitude"} <= set(df.columns):
        df = df[(df["latitude"].between(-90, 90)) & (df["longitude"].between(-180, 180))]
        df.dropna(subset=["latitude", "longitude"], inplace=True)

    print("df.columns:", df.columns)

    print("Step 2: Create Segments and Save to CSV !")
    # Group by MMSI and sort by timestamp within each group
    standardized_data = df.sort_values(['mmsi', 'timestamp'])
    
    # Create segments based on trajectory_len
    segments_list = []
    sequence_id = 0
    
    for mmsi, group in standardized_data.groupby('mmsi'):
        group = group.reset_index(drop=True)
        
        # Create segments of trajectory_len length
        for start_idx in range(0, len(group), args.trajectory_len):
            segment = group.iloc[start_idx:start_idx + args.trajectory_len].copy()
            
            # Only keep segments that have exactly trajectory_len rows
            if len(segment) == args.trajectory_len:
                segment.insert(0, 'sequence_id', sequence_id)
                
                segments_list.append(segment)
                sequence_id += 1
    
    standardized_data = pd.concat(segments_list, ignore_index=True)
    
    # Save the segmented data to a new CSV file
    segmented_data_file = args.raw_data_file.replace(".csv", "_standardized_with_SequenceId_SegementId_PointInfo_" + str(args.trajectory_len)+".csv").replace("CleanedFilteredData", "ProcessedData")
    segmented_data_dir = os.path.dirname(segmented_data_file)
    if not os.path.exists(segmented_data_dir):
        os.makedirs(segmented_data_dir)
    
    standardized_data['segment_id'] = (standardized_data.groupby('sequence_id').cumcount() // args.mini_segment_len).astype(int)
    standardized_data['dynamic_info'] = standardized_data.apply(lambda row: f"timestamp: {row['timestamp']},latitude: {row['latitude']}, longitude: {row['longitude']}, sog: {row['sog']}, cog: {row['cog']}, heading: {row['heading']}", axis=1)
    
    # TODO: add spatial context information for each point 
    '''
    print("Adding spatial context information for each point...")
    standardized_data['location_name'] = "unknown"
    standardized_data['shipping_lanes'] = "unknown"

    for i, ((seq_id, seg_id), group) in enumerate(standardized_data.groupby(['sequence_id', 'segment_id'])):      
        print(f"Progress: {i} segments processed")
        
        first_row = group.iloc[0]
        lat, lon = first_row['latitude'], first_row['longitude']
        
        if pd.notna(lat) and pd.notna(lon):
            location_name = reverse_geocode(lat, lon)
            lanes = get_shipping_lanes_osm(lat, lon)
            shipping_lanes = ", ".join(lanes) if lanes else "unknown"
            
            mask = (standardized_data['sequence_id'] == seq_id) & (standardized_data['segment_id'] == seg_id)
            standardized_data.loc[mask, 'location_name'] = location_name
            standardized_data.loc[mask, 'shipping_lanes'] = shipping_lanes
    '''
    standardized_data.to_csv(segmented_data_file, index=False)
    print(f"Segmented data saved to: {segmented_data_file}")

    return standardized_data

def get_missing_mark(args):

    trajectory_num = args.trajectory_num
    trajectory_len = args.trajectory_len
    mini_segment_len = args.mini_segment_len
    missing_ratio = args.missing_ratio
    
    # Calculate the number of segments per trajectory
    num_segments = trajectory_len // mini_segment_len 
    # Generate a binary matrix [trajectory_num, num_segments] where 0 has probability missing_ratio
    missing_blocks = np.random.choice([1, 0], 
                                    size=(trajectory_num, num_segments), 
                                    p=[missing_ratio, 1 - missing_ratio])

    return missing_blocks


def get_training_test_data(args):
    np.random.seed(args.seed)
    standardized_data_file = args.raw_data_file.replace(".csv", "_standardized_with_SequenceId_SegementId_PointInfo_" + str(args.trajectory_len)+"_" + str(args.trajectory_num)+".csv").replace("CleanedFilteredData", "ProcessedData")
    if os.path.exists(standardized_data_file):
        df = pd.read_csv(standardized_data_file)
    else:
        standardized_data_with_SequenceId = get_standardized_data_with_SequenceId(args)
        # Get total number of unique sequences
        total_sequences = standardized_data_with_SequenceId['sequence_id'].nunique()
        print(f"Total sequences available: {total_sequences}")
        
        # Randomly select trajectory_num sequences
        if total_sequences < args.trajectory_num:
            print(f"Warning: Requested {args.trajectory_num} trajectories but only {total_sequences} available. Using all available sequences.")
            selected_sequence_ids = standardized_data_with_SequenceId['sequence_id'].unique()
        else:
            selected_sequence_ids = np.random.choice(
                standardized_data_with_SequenceId['sequence_id'].unique(), 
                size=args.trajectory_num, 
                replace=False
            )
        
        # Filter the data to only include selected sequences
        standardized_data_with_SequenceId = standardized_data_with_SequenceId[
            standardized_data_with_SequenceId['sequence_id'].isin(selected_sequence_ids)
        ].reset_index(drop=True)
        
        print(f"Selected {len(selected_sequence_ids)} sequences for processing")
        print("standardized_data", standardized_data_with_SequenceId)

        standardized_data_with_SequenceId.to_csv(standardized_data_file, index=False)
        df = standardized_data_with_SequenceId

    # Get unique sequence IDs from the dataframe
    unique_sequence_ids = df['sequence_id'].unique()
    total_sequences = len(unique_sequence_ids)
    
    # Calculate training size based on training_test ratio
    training_size = int(total_sequences * args.training_test)
    
    # Randomly select sequence IDs for training and test sets
    np.random.shuffle(unique_sequence_ids)
    training_sequence_ids = unique_sequence_ids[:training_size]
    test_sequence_ids = unique_sequence_ids[training_size:]
    
    # Create training and test datasets based on selected sequence IDs
    training_df = df[df['sequence_id'].isin(training_sequence_ids)].reset_index(drop=True)
    test_df = df[df['sequence_id'].isin(test_sequence_ids)].reset_index(drop=True)
    
    print(f"Training set: {len(training_sequence_ids)} sequences, {len(training_df)} records")
    print(f"Test set: {len(test_sequence_ids)} sequences, {len(test_df)} records")

    mark_missing = get_missing_mark(args)
    mark_missing_training = mark_missing[:int(args.trajectory_num * args.training_test)]
    mark_missing_test = mark_missing[int(args.trajectory_num * args.training_test):]

    # training_df [trajectory_num * training_test, trajectory_len], save as a table 
    # testData [trajectory_num * training_test, trajectory_len], save as a table
    # mark_training [trajectory_num * training_test, trajectory_len/mini_segment_len] bool
    # mark_training [trajectory_num * training_test, trajectory_len/mini_segment_len] bool
    return ((training_df, mark_missing_training), (test_df, mark_missing_test))
