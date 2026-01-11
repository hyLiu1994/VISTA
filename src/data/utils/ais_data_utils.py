import os, requests, zipfile
from tqdm import tqdm

# Download raw data of AISDK and AISUS
def download_ais_dataset(file_name_list, raw_data_path):
    csv_file_path_list = []
    for file_name in file_name_list:
        # Step 1: Set base information about raw dataset
        global time_col_name, Lat_col_name, Lon_col_name, time_formulation
        if "aisdk" in file_name:
            download_url = "http://aisdata.ais.dk/2024/"
            csv_file_name = f"{file_name}.csv"
            if ("2006" in file_name):
                csv_file_name = file_name[:5] + "_" + file_name[5:].replace("-", "") + ".csv"
            # print(csv_file_name)
            time_col_name, Lat_col_name, Lon_col_name = "# Timestamp", "Latitude", "Longitude"
            time_formulation = "%d/%m/%Y %H:%M:%S"
        else: # https://coast.noaa.gov/htdata/CMSP/AISDataHandler/2024/index.html
            download_url = "https://coast.noaa.gov/htdata/CMSP/AISDataHandler/" + file_name[4:8] + "/"
            csv_file_name = f"{file_name}.csv"
            time_col_name, Lat_col_name, Lon_col_name = "BaseDateTime", "LAT", "LON"
            time_formulation = "%Y-%m-%dT%H:%M:%S"

        # Step 2: Check if CSV file already exists
        csv_file_path = os.path.join(raw_data_path, csv_file_name)

        if os.path.exists(csv_file_path):
            print(f"CSV file '{csv_file_path}' already exists. No download needed.")
            csv_file_path_list.append(csv_file_path)
            continue

        # Step 3: Download and unzip if CSV doesn't exist
        def attempt_download(url, zip_path):
            try:
                response = requests.get(url, stream=True)
                response.raise_for_status()
                total_length = int(response.headers.get('content-length'))
                with open(zip_path, 'wb') as file, tqdm(
                    desc=zip_path,
                    total=total_length,
                    unit='iB',
                    unit_scale=True,
                    unit_divisor=1024,
                ) as bar:
                    for chunk in response.iter_content(chunk_size=8192):
                        size = file.write(chunk)
                        bar.update(size)
                print(f"ZIP file downloaded successfully as {zip_path}")
                return True
            except requests.exceptions.HTTPError:
                return False

        # First attempt
        if not os.path.exists(raw_data_path):
            os.makedirs(raw_data_path)
        zip_path = os.path.join(raw_data_path, f"{file_name}.zip")
        url = download_url + file_name + ".zip"
        if not attempt_download(url, zip_path):
            # Second attempt
            url = download_url + file_name[:-3] + ".zip"
            zip_path = os.path.join(raw_data_path, f"{file_name[:-3]}.zip")
            if not attempt_download(url, zip_path):
                print(f"Error: Unable to download the file for {file_name}. The file may not exist.")
                return None

        def unzip_file(zip_path, extract_to):
            try:
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_to)
                    print(f"File '{zip_path}' has been unzipped.")
            except zipfile.BadZipFile:
                print(f"Error: The file '{zip_path}' is not a valid ZIP file.")
            except Exception as e:
                print(f"Error unzipping the file '{zip_path}': {e}")
        # Unzip the file
        unzip_file(zip_path, raw_data_path)

        # Check if CSV file now exists after unzipping
        if not os.path.exists(csv_file_path):
            print(f"Error: CSV file '{csv_file_path}' not found after unzipping.")
            return None

        csv_file_path_list.append(csv_file_path)
    print("raw_data_csv_file_path_list:", csv_file_path_list)
    return csv_file_path_list