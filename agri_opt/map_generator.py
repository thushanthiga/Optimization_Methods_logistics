import folium
import json

def generate_interactive_map(data, vehicle_routes, output_filename, title="OPTIMIZED ROUTES"):
    print(f"\n{'='*60}\n{title}\n{'='*60}")
    
    m = folium.Map(location=[7.8731, 80.7718], zoom_start=8, tiles='OpenStreetMap')
    colors = ['red', 'blue', 'green', 'purple', 'orange', 'darkred', 'cadetblue', 'darkgreen', 'darkblue', 'darkpurple', 'pink', 'lightblue', 'lightgreen', 'gray', 'black', 'lightgray']
    
    js_routes = []
    total_dist = 0
    
    for v_idx, route in vehicle_routes:
        if not route or len(route) < 2:
            continue
            
        print(f"Vehicle {v_idx} (Capacity: {data['vehicle_capacities'][v_idx]}kg) Route:")
        route_dist, route_load = 0, 0
        route_coords = []
        route_locations = []
        
        truck_group = folium.FeatureGroup(name=f"Truck {v_idx} (Depot {data['location_names'][route[0]]})")
        
        for i, node_index in enumerate(route):
            if i > 0 and node_index != route[0]: # don't add depot demand twice
                route_load += data['demands'][node_index]
                
            lat, lon = data['locations'][node_index][1][1], data['locations'][node_index][1][0]
            route_coords.append((lat, lon))
            loc_name = data['location_names'][node_index]
            route_locations.append({"name": loc_name, "lat": lat, "lon": lon})
            
            icon_color = 'black' if node_index < 5 else colors[v_idx % len(colors)]
            folium.Marker([lat, lon], popup=loc_name, icon=folium.Icon(color=icon_color)).add_to(truck_group)
            
            print(f"  {loc_name:<25} [Load: {route_load:4}kg] -> ")
            if i < len(route) - 1:
                route_dist += data['distance_matrix'][node_index][route[i+1]]
                
        folium.PolyLine(route_coords, color=colors[v_idx % len(colors)], weight=2.5, opacity=0.8).add_to(truck_group)
        truck_group.add_to(m)
        
        js_routes.append({"vehicle": v_idx, "locations": route_locations, "layer_id": truck_group.get_name(), "color": colors[v_idx % len(colors)]})
        
        print(f"  > Route Distance: {route_dist}km | Route Load: {route_load}kg\n")
        total_dist += route_dist
        
    print(f"{'='*60}\nTOTAL DISTANCE: {total_dist} km")
    
    folium.LayerControl().add_to(m)
    
    loc_names = data['location_names']
    loc_coords = {name: data['locations'][i][1] for i, name in enumerate(loc_names)}
    
    matrix_data = {}
    for i, name1 in enumerate(loc_names):
        matrix_data[name1] = {}
        for j, name2 in enumerate(loc_names):
            matrix_data[name1][name2] = {
                "dist": data['distance_matrix'][i][j],
                "time": data['time_matrix'][i][j]
            }

    all_locations = sorted(loc_names)
    options_html = "<option value=''>-- Select Point --</option>" + "".join([f"<option value='{loc}'>{loc}</option>" for loc in all_locations])
    
    js_content = open(output_filename.replace('.html', '_js.html'), 'r').read() if False else ""
    # We will inject the JS directly from a python multi-line string to avoid reading files
