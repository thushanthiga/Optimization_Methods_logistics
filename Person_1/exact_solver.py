import requests
import json
import folium
import os
import sys

# Add the parent directory to the path so we can import the shared agri_opt module
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
from agri_opt.data_model import create_data_model

# --- 2. EXACT SOLVER (MILP via OR-Tools) ---
def solve_routing():
    data = create_data_model()
    
    # Create Routing Index Manager for MULTI-DEPOT
    manager = pywrapcp.RoutingIndexManager(
        len(data['time_matrix']), 
        data['num_vehicles'], 
        data['starts'], 
        data['ends']
    )
    routing = pywrapcp.RoutingModel(manager)

    # Arc Cost Evaluator
    def distance_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return data['distance_matrix'][from_node][to_node]
    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    # Capacity Constraint (Heterogeneous)
    def demand_callback(from_index):
        from_node = manager.IndexToNode(from_index)
        return data['demands'][from_node]
    demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(
        demand_callback_index,
        0,  
        data['vehicle_capacities'], 
        True,  
        'Capacity'
    )

    # Time Window & Perishability Constraint
    def time_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return data['time_matrix'][from_node][to_node]
    time_callback_index = routing.RegisterTransitCallback(time_callback)
    routing.AddDimension(
        time_callback_index,
        30,  # wait time allowed
        600, # Perishability: Max 10 hours transit time per vehicle
        False,  
        'Time'
    )
    time_dimension = routing.GetDimensionOrDie('Time')

    for location_idx, time_window in enumerate(data['time_windows']):
        if location_idx in data['starts']: continue # Skip depots
        index = manager.NodeToIndex(location_idx)
        time_dimension.CumulVar(index).SetRange(time_window[0], time_window[1])

    # Allow dropping visits with high penalty if impossible (helps solver find a solution if overly constrained)
    penalty = 100000
    for node in range(5, len(data['time_matrix'])):
        routing.AddDisjunction([manager.NodeToIndex(node)], penalty)

    # Solve
    print("Running Exact Solver (MD-HVRPTW-P)...")
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION
    search_parameters.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    search_parameters.time_limit.seconds = 10 # Allow it to think for 10 seconds to find optimal
    
    solution = routing.SolveWithParameters(search_parameters)

    if solution:
        print_and_map_solution(data, manager, routing, solution)
    else:
        print("No solution found!")

# --- 3. GEOSPATIAL VISUALIZATION (Folium) ---
def print_and_map_solution(data, manager, routing, solution):
    print(f"\n{'='*60}\nMD-HVRPTW-P OPTIMIZED ROUTES\n{'='*60}")
    
    # Create base map centered on Sri Lanka
    m = folium.Map(location=[7.8731, 80.7718], zoom_start=8, tiles='OpenStreetMap')
    colors = ['red', 'blue', 'green', 'purple', 'orange', 'darkred']
    
    time_dimension = routing.GetDimensionOrDie('Time')
    total_dist, total_time = 0, 0
    
    for vehicle_id in range(data['num_vehicles']):
        index = routing.Start(vehicle_id)
        if routing.IsEnd(solution.Value(routing.NextVar(index))):
            continue # Vehicle not used
            
        print(f"Vehicle {vehicle_id} (Capacity: {data['vehicle_capacities'][vehicle_id]}kg) Route:")
        route_dist, route_load = 0, 0
        route_coords = []
        
        # Create a FeatureGroup for this specific truck so it can be toggled in the HTML
        truck_group = folium.FeatureGroup(name=f"Truck {vehicle_id} (Depot {data['location_names'][manager.IndexToNode(index)]})")
        
        while not routing.IsEnd(index):
            node_index = manager.IndexToNode(index)
            route_load += data['demands'][node_index]
            time_var = time_dimension.CumulVar(index)
            
            # Add to map
            lat, lon = data['locations'][node_index][1][1], data['locations'][node_index][1][0]
            route_coords.append((lat, lon))
            icon_color = 'black' if node_index < 5 else colors[vehicle_id % len(colors)]
            folium.Marker([lat, lon], popup=data['location_names'][node_index], icon=folium.Icon(color=icon_color)).add_to(truck_group)
            
            print(f"  {data['location_names'][node_index]:<25} [Load: {route_load:4}kg, Time: {solution.Min(time_var):3}m] -> ")
            previous_index = index
            index = solution.Value(routing.NextVar(index))
            route_dist += routing.GetArcCostForVehicle(previous_index, index, vehicle_id)
            
        node_index = manager.IndexToNode(index)
        time_var = time_dimension.CumulVar(index)
        lat, lon = data['locations'][node_index][1][1], data['locations'][node_index][1][0]
        route_coords.append((lat, lon))
        
        folium.PolyLine(route_coords, color=colors[vehicle_id % len(colors)], weight=2.5, opacity=0.8).add_to(truck_group)
        truck_group.add_to(m)
        
        print(f"  {data['location_names'][node_index]:<25} [Return Time: {solution.Min(time_var)}m]")
        print(f"  > Route Distance: {route_dist}km | Route Load: {route_load}kg\n")
        total_dist += route_dist
        total_time += solution.Min(time_var)
        
    print(f"{'='*60}\nTOTAL DISTANCE: {total_dist} km\nTOTAL TRANSIT TIME: {total_time} mins")
    
    # Add a layer control panel to toggle routes
    folium.LayerControl().add_to(m)
    
    # Save map
    map_path = os.path.join(os.path.dirname(__file__), "optimization_map.html")
    m.save(map_path)
    print(f"\n[SUCCESS] Interactive Geographic Map saved to: {map_path}")
    print("Open this HTML file in your browser for the presentation!")

if __name__ == '__main__':
    solve_routing()
