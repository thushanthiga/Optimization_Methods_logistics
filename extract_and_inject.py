import re

with open("Person_1/exact_solver.py", "r") as f:
    exact_code = f.read()

parts = exact_code.split('overlay_html = f"""')
if len(parts) < 2:
    print("Failed to find overlay_html")
    exit(1)
js_code_raw = 'overlay_html = f"""' + parts[1]
# Cut off everything after m.save
js_code = js_code_raw.split("if __name__ == '__main__':")[0]
js_code = js_code.replace("m.save('optimization_map.html')", "m.save('metaheuristic_map.html')")


with open("Person_2/metaheuristic_solver.py", "r") as f:
    meta_code = f.read()

# Append folium map generation to metaheuristic_solver.py
map_code = f"""
    # --- GEOSPATIAL VISUALIZATION ---
    import folium
    import json
    
    m = folium.Map(location=[7.8731, 80.7718], zoom_start=8, tiles='OpenStreetMap')
    colors = ['red', 'blue', 'green', 'purple', 'orange', 'darkred', 'cadetblue', 'darkgreen', 'darkblue', 'darkpurple', 'pink', 'lightblue', 'lightgreen', 'gray', 'black', 'lightgray']
    
    js_routes = []
    
    for v_idx, route in enumerate(best_routes):
        if not route: continue
        depot = DATA['starts'][v_idx]
        full_route = [depot] + route + [depot]
        
        route_coords = []
        route_locations = []
        truck_group = folium.FeatureGroup(name=f"Truck {{v_idx}} (Depot {{DATA['location_names'][depot]}})")
        
        for node_index in full_route:
            lat, lon = DATA['locations'][node_index][1][1], DATA['locations'][node_index][1][0]
            route_coords.append((lat, lon))
            loc_name = DATA['location_names'][node_index]
            route_locations.append({{"name": loc_name, "lat": lat, "lon": lon}})
            
            icon_color = 'black' if node_index < 5 else colors[v_idx % len(colors)]
            folium.Marker([lat, lon], popup=loc_name, icon=folium.Icon(color=icon_color)).add_to(truck_group)
            
        folium.PolyLine(route_coords, color=colors[v_idx % len(colors)], weight=2.5, opacity=0.8).add_to(truck_group)
        truck_group.add_to(m)
        
        js_routes.append({{"vehicle": v_idx, "locations": route_locations, "layer_id": truck_group.get_name(), "color": colors[v_idx % len(colors)]}})
        
    folium.LayerControl().add_to(m)
    
    loc_names = DATA['location_names']
    loc_coords = {{name: DATA['locations'][i][1] for i, name in enumerate(loc_names)}}
    
    matrix_data = {{}}
    for i, name1 in enumerate(loc_names):
        matrix_data[name1] = {{}}
        for j, name2 in enumerate(loc_names):
            matrix_data[name1][name2] = {{
                "dist": DATA['distance_matrix'][i][j],
                "time": DATA['time_matrix'][i][j]
            }}

    all_locations = sorted(loc_names)
    options_html = "<option value=''>-- Select Point --</option>" + "".join([f"<option value='{{loc}}'>{{loc}}</option>" for loc in all_locations])
    
    {js_code.replace('optimization_map.html', 'metaheuristic_map.html')}
    
if __name__ == '__main__':
    run_genetic_algorithm()
"""

if "# --- GEOSPATIAL VISUALIZATION ---" not in meta_code:
    meta_code = meta_code.replace('print(f"Total Distance Found via GA: {best_distance} km")', 'print(f"Total Distance Found via GA: {best_distance} km")\n' + map_code)
else:
    meta_code = meta_code.split("# --- GEOSPATIAL VISUALIZATION ---")[0]
    meta_code += map_code

with open("Person_2/metaheuristic_solver.py", "w") as f:
    f.write(meta_code)

print("Injected map generation into metaheuristic_solver.py!")
