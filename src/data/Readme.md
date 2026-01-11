# AIS (Automatic Identification System) dataset
## Overview

This directory contains components for processing AIS (Automatic Identification System) maritime data from official platforms.
The system provides a **complete data processing pipeline** for:

* **Downloading** raw AIS CSV files from official maritime data sources.
* **Standardizing** heterogeneous data formats from different regions (Denmark and the U.S.).
* **Cleaning and filtering** vessel trajectories based on time intervals.
* **Saving** both processed data and summary statistics for downstream trajectory analysis.

## Supported Data Sources

* **AIS-DK (Denmark)**: [Danish Maritime Authority AIS Data Platform](http://aisdata.ais.dk/)
* **AIS-US (United States)**: [NOAA Coast AIS Data Platform](https://coast.noaa.gov/htdata/CMSP/AISDataHandler/2024/index.html)

Each data source provides compressed CSV files containing ship position reports (`mmsi`, `lat`, `lon`, `timestamp`, etc.) for a given day.

## Arguments

| Argument              | Type        | Default                 | Description                                                                                                                                                            |
| --------------------- | ----------- | ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `--datasets`          | `List[str]` | `['AIS_2024_04_02@02']` | The dataset(s) to download and process. Format: `DatasetStart@EndIndex`. Example: `AIS_2024_04_01@05` will process datasets from `AIS_2024_04_01` to `AIS_2024_04_05`. |
| `--min_time_interval` | `int`       | `360`                   | Minimum time interval (in seconds) between two AIS records within the same trajectory. If time difference < `min_time_interval`, the record is skipped.                |
| `--max_time_interval` | `int`       | `1e9`                   | Maximum time interval (in seconds) allowed between consecutive points within the same trajectory. If exceeded, a new trajectory (`TrajID`) is started.                 |


## Example Usage

Run the script directly:

```bash
python ais_dataset.py --datasets AIS_2024_04_01@03 --min_time_interval 600 --max_time_interval 86400
```

This will:

1. Download AIS data from `AIS_2024_04_01`, `AIS_2024_04_02`, and `AIS_2024_04_03`.
2. Clean and standardize columns (harmonizing AIS-DK and AIS-US field names).
3. Generate filtered trajectories where each point is at least **600 seconds (10 minutes)** apart and no gap exceeds **86400 seconds (1 day)**.
4. Save processed files and summary statistics under the `data/` directory.

## Directory Structure

After running the pipeline, the directory structure will look like this:

```
project_root/
└── data/
    ├── RawData/                     # Raw AIS CSVs downloaded from official platforms
    │   ├── AIS_2024_04_01.csv
    │   ├── AIS_2024_04_02.csv
    │   └── AIS_2024_04_03.csv
    │
    └── CleanedFilteredData/
        ├── AIS_2024_04_01@03_cleaned.csv
        ├── AIS_2024_04_01@03_filtered600_86400.csv
        ├── cleaned_data_statistics.csv
        └── filtered_data_statistics.csv
```

## Output Files

| File                           | Description                                                                         |
| ------------------------------ | ----------------------------------------------------------------------------------- |
| `*_cleaned.csv`                | Standardized AIS dataset after cleaning and column mapping.                         |
| `*_filtered[min]_[max].csv`    | Final filtered dataset with assigned trajectory IDs (`TrajID`).                     |
| `cleaned_data_statistics.csv`  | Summary statistics (unique MMSI, record count, file size) for all cleaned datasets. |
| `filtered_data_statistics.csv` | Statistics for all filtered datasets, including number of trajectories.             |

