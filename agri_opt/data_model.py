import csv
import os
import json

def create_data_model():
    """Loads the massive 75-node dataset and cached matrix."""
    data = {}
    
    csv_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'locations_demand.csv')
    matrix_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'distance_matrix.json')
    
    locations = []
    demands = []
    time_windows = []
    
    # Read Locations and Demands
    with open(csv_path, mode='r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            loc_name = f"{row['type']}: {row['name']}"
            lat = float(row['latitude'])
            lon = float(row['longitude'])
            demand = int(row['demand_kg'])
            tw_start = int(row['time_window_start_min'])
            tw_end = int(row['time_window_end_min'])
            
            locations.append((loc_name, [lon, lat]))
            demands.append(demand)
            time_windows.append((tw_start, tw_end))
            
    # Read Cached OSRM Matrix (75x75)
    with open(matrix_path, 'r') as file:
        matrix_data = json.load(file)
        
    data['locations'] = locations
    data['location_names'] = [loc[0] for loc in locations]
    data['distance_matrix'] = matrix_data['distances']
    data['time_matrix'] = matrix_data['durations']

    data['demands'] = demands
    data['time_windows'] = time_windows

    # 5 Depots (indices 0 to 4). We assign 6 trucks to each depot.
    data['num_vehicles'] = 30
    
    starts = []
    ends = []
    capacities = []
    
    # Large FMCG Logistics Trucks
    for depot_idx in range(5):
        for _ in range(6):
            starts.append(depot_idx)
            ends.append(depot_idx)
            # Mix of heavy 25-ton and standard 15-ton lorries
            capacity = 25000 if _ % 2 == 0 else 15000
            capacities.append(capacity)
            
    data['starts'] = starts
    data['ends'] = ends
    data['vehicle_capacities'] = capacities

    return data

DATA = create_data_model()
