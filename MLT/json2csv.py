import json
import csv

def meta_to_csv(meta_file_path, csv_file_path):
    # Load the meta.json file
    with open(meta_file_path, 'r') as f:
        meta_data = json.load(f)
    
    # Open the CSV file for writing
    with open(csv_file_path, 'w', newline='') as csvfile:
        # Define the CSV headers (excluding 'frame_centroids')
        headers = ["fname", "set", "num_sounds_without_noise", "global_centroid"]
        writer = csv.DictWriter(csvfile, fieldnames=headers)
        
        # Write the header to the CSV
        writer.writeheader()
        
        # Write each entry to the CSV
        for entry in meta_data:
            # Create a row dictionary with the required fields
            row = {
                "fname": entry["fname"],
                "set": ",".join(entry["set"]),
                "num_sounds_without_noise": entry["num_sounds_without_noise"],
                "global_centroid": entry.get("global_centroid", "")
            }
            writer.writerow(row)

# Define file paths
meta_file_path = "meta.json"  # Path to meta.json
csv_file_path = "output.csv"  # Output CSV file path

# Convert meta.json to CSV
meta_to_csv(meta_file_path, csv_file_path)
