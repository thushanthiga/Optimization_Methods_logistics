import requests
import csv
import os
import json

def get_real_locations():
    # 80 Real Cities/Towns across Sri Lanka
    towns = [
        {"name": "Colombo", "lat": 6.9271, "lon": 79.8612},
        {"name": "Kandy", "lat": 7.2906, "lon": 80.6367},
        {"name": "Galle", "lat": 6.0328, "lon": 80.2170},
        {"name": "Jaffna", "lat": 9.6615, "lon": 80.0255},
        {"name": "Trincomalee", "lat": 8.5874, "lon": 81.2152},
        {"name": "Negombo", "lat": 7.2088, "lon": 79.8358},
        {"name": "Anuradhapura", "lat": 8.3114, "lon": 80.4037},
        {"name": "Kurunegala", "lat": 7.4833, "lon": 80.3667},
        {"name": "Ratnapura", "lat": 6.6828, "lon": 80.4020},
        {"name": "Badulla", "lat": 6.9847, "lon": 81.0593},
        {"name": "Matara", "lat": 5.9549, "lon": 80.5353},
        {"name": "Batticaloa", "lat": 7.7170, "lon": 81.6989},
        {"name": "Puttalam", "lat": 8.0362, "lon": 79.8283},
        {"name": "Polonnaruwa", "lat": 7.9403, "lon": 81.0188},
        {"name": "Nuwara Eliya", "lat": 6.9497, "lon": 80.7828},
        {"name": "Dambulla", "lat": 7.8674, "lon": 80.6496},
        {"name": "Ampara", "lat": 7.2912, "lon": 81.6724},
        {"name": "Matale", "lat": 7.4725, "lon": 80.6234},
        {"name": "Kalutara", "lat": 6.5854, "lon": 79.9598},
        {"name": "Vavuniya", "lat": 8.7514, "lon": 80.4971},
        {"name": "Chilaw", "lat": 7.5758, "lon": 79.7953},
        {"name": "Mannar", "lat": 8.9810, "lon": 79.9044},
        {"name": "Kilinochchi", "lat": 9.3803, "lon": 80.4022},
        {"name": "Mullaitivu", "lat": 9.2671, "lon": 80.8142},
        {"name": "Monaragala", "lat": 6.8728, "lon": 81.3489},
        {"name": "Kegalle", "lat": 7.2513, "lon": 80.3462},
        {"name": "Gampaha", "lat": 7.0873, "lon": 79.9942},
        {"name": "Hambantota", "lat": 6.1246, "lon": 81.1213},
        {"name": "Bandarawela", "lat": 6.8301, "lon": 80.9822},
        {"name": "Weligama", "lat": 5.9737, "lon": 80.4286},
        {"name": "Moratuwa", "lat": 6.7730, "lon": 79.8805},
        {"name": "Panadura", "lat": 6.7110, "lon": 79.9071},
        {"name": "Nugegoda", "lat": 6.8649, "lon": 79.8860},
        {"name": "Maharagama", "lat": 6.8480, "lon": 79.9238},
        {"name": "Wattala", "lat": 6.9898, "lon": 79.8906},
        {"name": "Dehiwala", "lat": 6.8398, "lon": 79.8735},
        {"name": "Avissawella", "lat": 6.9535, "lon": 80.2120},
        {"name": "Kaduwela", "lat": 6.9328, "lon": 79.9836},
        {"name": "Homagama", "lat": 6.8427, "lon": 80.0034},
        {"name": "Ja-Ela", "lat": 7.0792, "lon": 79.8897},
        {"name": "Kandana", "lat": 7.0435, "lon": 79.8966},
        {"name": "Minuwangoda", "lat": 7.1672, "lon": 79.9458},
        {"name": "Nittambuwa", "lat": 7.1437, "lon": 80.0934},
        {"name": "Gampola", "lat": 7.1601, "lon": 80.5707},
        {"name": "Nawalapitiya", "lat": 7.0560, "lon": 80.5332},
        {"name": "Hatton", "lat": 6.8893, "lon": 80.5974},
        {"name": "Thalawakele", "lat": 6.9388, "lon": 80.6586},
        {"name": "Wattegama", "lat": 7.3486, "lon": 80.6841},
        {"name": "Kadugannawa", "lat": 7.2558, "lon": 80.5186},
        {"name": "Kuliyapitiya", "lat": 7.4695, "lon": 80.0401},
        {"name": "Narammala", "lat": 7.4277, "lon": 80.2117},
        {"name": "Wariyapola", "lat": 7.6254, "lon": 80.2227},
        {"name": "Maho", "lat": 7.8222, "lon": 80.2974},
        {"name": "Galewela", "lat": 7.7663, "lon": 80.5746},
        {"name": "Sigiriya", "lat": 7.9541, "lon": 80.7547},
        {"name": "Habarana", "lat": 8.0347, "lon": 80.7483},
        {"name": "Kekirawa", "lat": 8.0366, "lon": 80.5898},
        {"name": "Eppawala", "lat": 8.1469, "lon": 80.3957},
        {"name": "Tambuttegama", "lat": 8.1492, "lon": 80.2925},
        {"name": "Nochchiyagama", "lat": 8.2464, "lon": 80.2319},
        {"name": "Medawachchiya", "lat": 8.5361, "lon": 80.4957},
        {"name": "Horana", "lat": 6.7196, "lon": 80.0632},
        {"name": "Matugama", "lat": 6.5236, "lon": 80.1132},
        {"name": "Agalawatta", "lat": 6.4719, "lon": 80.1477},
        {"name": "Beruwala", "lat": 6.4788, "lon": 79.9829},
        {"name": "Ambalangoda", "lat": 6.2346, "lon": 80.0537},
        {"name": "Hikkaduwa", "lat": 6.1362, "lon": 80.1039},
        {"name": "Elpitiya", "lat": 6.2690, "lon": 80.1584},
        {"name": "Tangalle", "lat": 6.0246, "lon": 80.7951},
        {"name": "Beliatta", "lat": 6.0461, "lon": 80.7570},
        {"name": "Dikwella", "lat": 5.9686, "lon": 80.6974},
        {"name": "Tissamaharama", "lat": 6.2801, "lon": 81.2872},
        {"name": "Kataragama", "lat": 6.4138, "lon": 81.3323},
        {"name": "Middeniya", "lat": 6.1436, "lon": 80.7439},
        {"name": "Walasmulla", "lat": 6.1396, "lon": 80.6558}
    ]
    return towns

def get_osrm_matrix(coords):
    print(f"Fetching OSRM Distance Matrix for {len(coords)} locations...")
    # OSRM public API limit is 100 coordinates
    coords_string = ";".join([f"{lon},{lat}" for lon, lat in coords])
    url = f"http://router.project-osrm.org/table/v1/driving/{coords_string}?annotations=distance,duration"
    
    try:
        response = requests.get(url)
        data = response.json()
        if data.get("code") != "Ok":
             print("OSRM Error:", data.get("code"))
             return None, None
             
        durations = [[int(val / 60) for val in row] for row in data["durations"]]
        distances = [[int(val / 1000) for val in row] for row in data["distances"]]
        return distances, durations
    except Exception as e:
        print(f"Error calling OSRM: {e}")
        return None, None

def main():
    all_locations = get_real_locations()
    
    # We will treat the first 5 towns as our Depots (Colombo, Kandy, Galle, Jaffna, Trincomalee)
    
    coords = [[loc['lon'], loc['lat']] for loc in all_locations]
    distances, durations = get_osrm_matrix(coords)
    
    if not distances:
        print("Failed to build matrix from OSRM.")
        return
        
    csv_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'locations_demand.csv')
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    
    with open(csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['id', 'type', 'name', 'latitude', 'longitude', 'demand_kg', 'time_window_start_min', 'time_window_end_min'])
        
        for idx, loc in enumerate(all_locations):
            loc_type = "Depot" if idx < 5 else "Market"
            # Real world demand proxy: Deterministic generation based on lat/lon digits
            demand = 0 if loc_type == "Depot" else (int(str(loc['lat'])[-3:]) * 15) % 8000 + 1000 
            
            tw_start = 60 # 1 hour
            tw_end = 900 # 15 hours
            if loc_type == "Depot":
                tw_start, tw_end = 0, 1440
                
            writer.writerow([idx, loc_type, loc['name'], loc['lat'], loc['lon'], demand, tw_start, tw_end])

    print(f"Massive 75-Node Dataset written to {csv_path}")
    
    matrix_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'distance_matrix.json')
    with open(matrix_path, 'w') as f:
        json.dump({'distances': distances, 'durations': durations}, f)
    print(f"OSRM 75x75 Matrix cached to {matrix_path}")

if __name__ == "__main__":
    main()
