import argparse, os, sys
import pandas as pd
from src.data.utils.ais_data_utils import download_ais_dataset

current_path = os.path.dirname(os.path.abspath(__file__))
parent_current_path = os.path.dirname(current_path)
root_path = os.path.dirname(parent_current_path)
sys.path.append(root_path)


def hyperparameter_configure_ais_dataset(parser):
    dataset_group = parser.add_argument_group('Dataset Configuration')
    dataset_group.add_argument("--datasets", type=str, default=['AIS_2024_04_02@02'], nargs="+")
    dataset_group.add_argument("--min_time_interval", type=int, default=360)
    dataset_group.add_argument("--max_time_interval", type=int, default=1e9)

class AISDataset():
    '''
    AISDataset class for processing AIS (Automatic Identification System) data.
    
    This class handles raw CSV data downloaded from official AIS platforms:
    - AIS-DK: Danish Maritime Authority AIS data platform
    - AIS-US: United States AIS data platform
    
    The class provides functionality to load, standardize, and filter maritime trajectory data from these sources for further analysis and utilization.
    '''
    def get_dataset_identifier(self, args):
        return self.dataset_identifier + "_filtered"+ str(args.min_time_interval)+ "_" + str(args.max_time_interval)

    def __init__(self, args):
        self.dataset_identifier = ''
        if len(args.datasets) == 1:
            self.dataset_identifier = args.datasets[0]
        elif len(args.datasets) > 1:
            self.dataset_identifier = args.datasets[0] + args.datasets[-1]
        self.min_time_interval = args.min_time_interval
        self.max_time_interval = args.max_time_interval

        self.raw_data_dir = f'{root_path}/data/RawData/'
        self.CleanedFiltered_data_dir = f'{root_path}/data/CleanedFilteredData/'

        self.cleaned_data_file = self.CleanedFiltered_data_dir + self.dataset_identifier + "_cleaned.csv"
        self.filtered_data_file = self.CleanedFiltered_data_dir + self.dataset_identifier + "_filtered" + str(args.min_time_interval)+ "_" + str(int(args.max_time_interval))+ ".csv"
        self.cleaned_data_statistics_file = self.CleanedFiltered_data_dir + "cleaned_data_statistics.csv"
        self.filtered_data_statistics_file = self.CleanedFiltered_data_dir + "filtered_data_statistics.csv"

        if not os.path.exists(self.filtered_data_file):
            print("Do not find filtered data, begin prepare filtered data:", self.dataset_identifier)
            if not os.path.exists(self.cleaned_data_file):
                print("Do not find cleaned data, begin prepare cleaned data:", self.dataset_identifier)
                csv_file_list = self.prepare_raw_data(args.datasets)
                self.prepare_clean_and_standardize_data(csv_file_list)
            self.prepare_filtered_data()

    def load_cleaned_data(self):
        return pd.read_csv(self.cleaned_data_file)

    # Prepare raw data: download raw AIS dataset from official AIS platforms
    def prepare_raw_data(self, datasets):
        file_name_list = []
        for dataset in datasets:
            dataset_start, dataset_end = dataset.split("@")[0], int(dataset.split("@")[1])
            file_names = [dataset_start[:-2] + str(i).zfill(2) for i in
                        range(int(dataset_start.split(dataset_start[-3])[-1]), int(dataset_end) + 1)]
        file_name_list.extend(file_names)
        print("file_name_list:", file_name_list)
        csv_file_list = download_ais_dataset(file_name_list, self.raw_data_dir)
        return csv_file_list

    # Prepare clean and standardize data
    def prepare_clean_and_standardize_data(self, csv_file_list):
        # Step 1: Clean data & Standardize data columns
        print("begin clean and standardize ais_dataset:", self.dataset_identifier)
        df_list = []
        for csv_file in csv_file_list:
            print(f"Reading file: {csv_file}")
            df = pd.read_csv(csv_file)
            from src.data.utils.ais_data_filter import denmark_ais_data_filter, american_ais_data_filter
            if ("aisdk" in csv_file):
                df = denmark_ais_data_filter(df)
            else:
                df = american_ais_data_filter(df)
            df_list.append(df)
        df = pd.concat(df_list, ignore_index=True)

        from src.data.utils.AISDataMappingDicts import ColumnName_Standard_Mapping_US2DK, ColumnName_Standard_Mapping_DK2Standard
        df.rename(columns=ColumnName_Standard_Mapping_US2DK, inplace=True)
        df.rename(columns=ColumnName_Standard_Mapping_DK2Standard, inplace=True)
        # Convert timestamp format for Danish (aisdk) datasets
        if any("aisdk" in csv_file for csv_file in csv_file_list):
            df["timestamp"] = pd.to_datetime(df["timestamp"], format="%d/%m/%Y %H:%M:%S", errors="coerce")
        else:
            df["timestamp"] = pd.to_datetime(df["timestamp"], format="%Y-%m-%dT%H:%M:%S", errors="coerce")
        
        if not os.path.exists(self.CleanedFiltered_data_dir):
            os.makedirs(self.CleanedFiltered_data_dir)
        df.to_csv(self.cleaned_data_file, index=False)

        # Step 2: Statistical analysis of the dataset
        unique_mmsi_count = df['mmsi'].nunique()
        total_records = len(df)
        data_size_mb = os.path.getsize(self.cleaned_data_file) / (1024 * 1024)
        
        # Save statistics to CSV file
        stats_data = {
            'Dataset Identifier': [self.dataset_identifier + "_cleaned.csv"],
            'Number of unique MMSI': [unique_mmsi_count],
            'Total number of records': [total_records],
            'Datasize': [f"{data_size_mb:.2f} MB"]
        }
        stats_df = pd.DataFrame(stats_data)
        if os.path.exists(self.cleaned_data_statistics_file):
            existing_df = pd.read_csv(self.cleaned_data_statistics_file)
            stats_df = pd.concat([existing_df, stats_df], ignore_index=True)
        stats_df.to_csv(self.cleaned_data_statistics_file, index=False)

        print("end clean and standardize ais_dataset:", self.dataset_identifier)

    def prepare_filtered_data(self):
        df = pd.read_csv(self.cleaned_data_file)
        # Convert timestamp to datetime if it's not already
        if df['timestamp'].dtype == 'object':
            df['timestamp'] = pd.to_datetime(df['timestamp'], format='%Y-%m-%d %H:%M:%S')
        
        # Sort by MMSI and timestamp
        df = df.sort_values(['mmsi', 'timestamp']).reset_index(drop=True)
        
        # Initialize TrajID column
        df['TrajID'] = -1
        traj_id = 0
        
        for mmsi, group in df.groupby('mmsi'):
            group_indices = group.index.tolist()
            if len(group_indices) == 0:
                continue
                
            current_traj_start_idx = group_indices[0]
            df.loc[current_traj_start_idx, 'TrajID'] = traj_id
            last_selected_time = df.loc[current_traj_start_idx, 'timestamp']
            
            for idx in group_indices[1:]:
                current_time = df.loc[idx, 'timestamp']
                time_diff = (current_time - last_selected_time).total_seconds()
                
                if time_diff > self.max_time_interval:
                    traj_id += 1
                    df.loc[idx, 'TrajID'] = traj_id
                    last_selected_time = current_time
                elif time_diff >= self.min_time_interval:
                    df.loc[idx, 'TrajID'] = traj_id
                    last_selected_time = current_time
            
            traj_id += 1
        
        # Filter out records that weren't assigned to any trajectory
        df = df[df['TrajID'] != -1]
        df.to_csv(self.filtered_data_file, index=False)
        
        # Record statistics for filtered data
        unique_mmsi = df['mmsi'].nunique()
        total_records = len(df)
        unique_trajectories = df['TrajID'].nunique()
        
        # Calculate file size
        file_size_bytes = os.path.getsize(self.filtered_data_file)
        data_size_mb = file_size_bytes / (1024 * 1024)
        
        # Create statistics data
        stats_data = {
            'Dataset Identifier': [f"{self.dataset_identifier}_filtered" + str(self.min_time_interval) + "_" + str(self.max_time_interval)],
            'Number of unique MMSI': [unique_mmsi],
            'Total number of records': [total_records],
            'Number of trajectories': [unique_trajectories],
            'Datasize': [f"{data_size_mb:.2f} MB"]
        }
        
        # Save statistics
        stats_df = pd.DataFrame(stats_data)
        if os.path.exists(self.filtered_data_statistics_file):
            existing_df = pd.read_csv(self.filtered_data_statistics_file)
            stats_df = pd.concat([existing_df, stats_df], ignore_index=True)
        stats_df.to_csv(self.filtered_data_statistics_file, index=False)
    

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    hyperparameter_configure_ais_dataset(parser)
    args = parser.parse_args()
    print("args:", args)
    # args.datasets = ['AIS_2024_01_01@01']
    AISDataset(args)