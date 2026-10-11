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
    
    # --- JS INJECTION FOR FROM/TO FILTER ---
    # We will build a JS object containing route information so the client-side can filter.
    js_routes = []
    
    time_dimension = routing.GetDimensionOrDie('Time')
    total_dist, total_time = 0, 0
    
    for vehicle_id in range(data['num_vehicles']):
        index = routing.Start(vehicle_id)
        if routing.IsEnd(solution.Value(routing.NextVar(index))):
            continue # Vehicle not used
            
        print(f"Vehicle {vehicle_id} (Capacity: {data['vehicle_capacities'][vehicle_id]}kg) Route:")
        route_dist, route_load = 0, 0
        route_coords = []
        route_locations = []
        
        # Create a FeatureGroup for this specific truck so it can be toggled in the HTML
        truck_group = folium.FeatureGroup(name=f"Truck {vehicle_id} (Depot {data['location_names'][manager.IndexToNode(index)]})")
        
        while not routing.IsEnd(index):
            node_index = manager.IndexToNode(index)
            route_load += data['demands'][node_index]
            time_var = time_dimension.CumulVar(index)
            
            # Add to map
            lat, lon = data['locations'][node_index][1][1], data['locations'][node_index][1][0]
            route_coords.append((lat, lon))
            loc_name = data['location_names'][node_index]
            route_locations.append({"name": loc_name, "lat": lat, "lon": lon})
            
            icon_color = 'black' if node_index < 5 else colors[vehicle_id % len(colors)]
            folium.Marker([lat, lon], popup=loc_name, icon=folium.Icon(color=icon_color)).add_to(truck_group)
            
            print(f"  {loc_name:<25} [Load: {route_load:4}kg, Time: {solution.Min(time_var):3}m] -> ")
            previous_index = index
            index = solution.Value(routing.NextVar(index))
            route_dist += routing.GetArcCostForVehicle(previous_index, index, vehicle_id)
            
        node_index = manager.IndexToNode(index)
        time_var = time_dimension.CumulVar(index)
        lat, lon = data['locations'][node_index][1][1], data['locations'][node_index][1][0]
        route_coords.append((lat, lon))
        loc_name = data['location_names'][node_index]
        route_locations.append({"name": loc_name, "lat": lat, "lon": lon})
        
        folium.PolyLine(route_coords, color=colors[vehicle_id % len(colors)], weight=2.5, opacity=0.8).add_to(truck_group)
        truck_group.add_to(m)
        
        js_routes.append({"vehicle": vehicle_id, "locations": route_locations, "layer_id": truck_group.get_name(), "color": colors[vehicle_id % len(colors)]})
        
        print(f"  {data['location_names'][node_index]:<25} [Return Time: {solution.Min(time_var)}m]")
        print(f"  > Route Distance: {route_dist}km | Route Load: {route_load}kg\n")
        total_dist += route_dist
        total_time += solution.Min(time_var)
        
    print(f"{'='*60}\nTOTAL DISTANCE: {total_dist} km\nTOTAL TRANSIT TIME: {total_time} mins")
    
    # Add a layer control panel to toggle routes
    folium.LayerControl().add_to(m)
    
    # Prepare dropdown options and matrix mapping
    loc_names = data['location_names']
    loc_coords = {name: data['locations'][i][1] for i, name in enumerate(loc_names)}
    
    # Create distance and time lookup tables for JS
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
    
    # Custom HTML/JS overlay (No internal UI, relies on master dashboard)
    overlay_html = f"""
    <div id="ui-panel" style="position: fixed; top: 10px; left: 50px; z-index: 9999; pointer-events: none;">
        <div id="filter_msg" style="margin-top: 10px; font-size: 0.9em; color: #333;"></div>
    </div>
    
    <script>
        var routeData = {json.dumps(js_routes)};
        var matrixData = {json.dumps(matrix_data)};
        var locCoords = {json.dumps(loc_coords)};
        var mapInstance = null;
        var customLine = null;
        var startMarker = null;
        var endMarker = null;

        function applyFilter(fromPt, toPt) {{
            var msg = document.getElementById('filter_msg');
            msg.innerHTML = "Calculating true road route...";
            
            if (customLine && mapInstance) {{
                mapInstance.removeLayer(customLine);
                customLine = null;
            }}
            if (startMarker && mapInstance) {{
                mapInstance.removeLayer(startMarker);
                startMarker = null;
            }}
            if (endMarker && mapInstance) {{
                mapInstance.removeLayer(endMarker);
                endMarker = null;
            }}
            
            if (!fromPt || !toPt) {{
                msg.innerHTML = "<span style='color:red;'>Please select both points.</span>";
                return;
            }}
            
            var msgContent = "";
            
            // 1. Point-to-Point direct data from the underlying matrix
            var directData = matrixData[fromPt][toPt];
            msgContent += "<strong>Direct API Data:</strong><br/>";
            msgContent += "Distance: " + directData.dist + " km<br/>";
            msgContent += "Time: " + directData.time + " mins<br/><hr style='margin:5px 0;'/>";
            
            // 2. Hide all existing truck layers on the map
            if (mapInstance) {{
                for (var i = 0; i < routeData.length; i++) {{
                    var layer = window[routeData[i].layer_id];
                    if (layer && mapInstance.hasLayer(layer)) {{
                        mapInstance.removeLayer(layer);
                    }}
                }}
            }}
            
            if (fromPt === toPt) {{
                msg.innerHTML = "<strong>Direct API Data:</strong><br/>Distance: 0 km<br/>Time: 0 mins<br/><br/><strong style='color:#28a745;'>✓ You are already at the destination!</strong>";
                if (mapInstance) {{
                    var coords = [locCoords[fromPt][1], locCoords[fromPt][0]];
                    startMarker = L.marker(coords, {{title: fromPt}}).bindPopup("<b>" + fromPt + "</b>").addTo(mapInstance);
                    mapInstance.setView(coords, 13);
                }}
                return;
            }}
            
            function animateTruckAlong(latlngs, truckColors) {{
                if (!truckColors || truckColors.length === 0) truckColors = ['#007bff'];
                if (window.movingTruckMarker && mapInstance) {{
                    mapInstance.removeLayer(window.movingTruckMarker);
                }}
                
                function getIcon(color) {{
                    var isTransfer = (color === '#333333');
                    var svg;
                    if (isTransfer) {{
                        // Package/Box icon
                        svg = `<svg viewBox="0 0 512 512" width="28" height="28" xmlns="http://www.w3.org/2000/svg"><path fill="#ff9900" stroke="black" stroke-width="15" d="M256 16L31 120.3 256 224l225-103.7L256 16zM31 161.4V375.9L256 480v-214.6L31 161.4zM288 480V265.4L513 161.4V375.9L288 480z"/></svg>`;
                    }} else {{
                        // Truck icon
                        svg = `<svg viewBox="0 0 640 512" width="32" height="32" xmlns="http://www.w3.org/2000/svg"><path fill="${{color}}" stroke="black" stroke-width="15" d="M48 0C21.5 0 0 21.5 0 48l0 368c0 26.5 21.5 48 48 48l16 0c0 44.2 35.8 80 80 80s80-35.8 80-80l160 0c0 44.2 35.8 80 80 80s80-35.8 80-80l32 0c44.2 0 80-35.8 80-80l0-160-224 0 0-208C352 21.5 330.5 0 304 0L48 0zM576 208l0 144c0 8.8-7.2 16-16 16l-32 0c0-44.2-35.8-80-80-80s-80 35.8-80 80l-64 0 0-160 272 0zM144 464a32 32 0 1 1 0-64 32 32 0 1 1 0 64zm304 0a32 32 0 1 1 0-64 32 32 0 1 1 0 64z"/></svg>`;
                    }}
                    return L.divIcon({{
                        html: "<div style='filter: drop-shadow(2px 2px 2px rgba(255,255,255,0.8)); transform: scaleX(-1); margin-top:-16px; margin-left:-16px;'>" + svg + "</div>",
                        className: '',
                        iconSize: [32, 32],
                        iconAnchor: [16, 16]
                    }});
                }}
                
                var currentTruckIdx = 0;
                window.movingTruckMarker = L.marker(latlngs[0], {{icon: getIcon(truckColors[0]), zIndexOffset: 1000}}).addTo(mapInstance);
                
                var duration = 5000;
                var startTime = null;
                var totalDist = 0;
                var dists = [0];
                for(var j=1; j<latlngs.length; j++) {{
                    var p1 = mapInstance.project(latlngs[j-1]);
                    var p2 = mapInstance.project(latlngs[j]);
                    totalDist += p1.distanceTo(p2);
                    dists.push(totalDist);
                }}
                
                var lastTruckIdx = 0;
                function step(timestamp) {{
                    if (!startTime) startTime = timestamp;
                    var progress = (timestamp - startTime) / duration;
                    if (progress > 1) progress = 1;
                    
                    var expectedTruckIdx = Math.floor(progress * truckColors.length);
                    if (expectedTruckIdx >= truckColors.length) expectedTruckIdx = truckColors.length - 1;
                    
                    if (expectedTruckIdx !== lastTruckIdx) {{
                        var color = truckColors[expectedTruckIdx];
                        window.movingTruckMarker.setIcon(getIcon(color));
                        if (color === '#333333') {{
                            window.movingTruckMarker.bindPopup("<b>3rd Party Courier in transit...</b>").openPopup();
                        }} else if (lastTruckIdx !== undefined && truckColors[lastTruckIdx] === '#333333') {{
                            window.movingTruckMarker.bindPopup("<b>Goods Loaded!</b>").openPopup();
                        }}
                        setTimeout(() => window.movingTruckMarker.closePopup(), 1500);
                        lastTruckIdx = expectedTruckIdx;
                    }}
                    
                    var currentDist = progress * totalDist;
                    var segmentIdx = 0;
                    for(var j=1; j<dists.length; j++) {{
                        if (currentDist <= dists[j]) {{ segmentIdx = j; break; }}
                    }}
                    if (segmentIdx === 0 && dists.length > 1) segmentIdx = 1;
                    if (segmentIdx > 0 && segmentIdx < latlngs.length) {{
                        var segStart = dists[segmentIdx-1];
                        var segEnd = dists[segmentIdx];
                        var segProgress = (segEnd === segStart) ? 1 : (currentDist - segStart) / (segEnd - segStart);
                        var p1 = latlngs[segmentIdx-1];
                        var p2 = latlngs[segmentIdx];
                        var currentLat = p1[0] + (p2[0] - p1[0]) * segProgress;
                        var currentLng = p1[1] + (p2[1] - p1[1]) * segProgress;
                        window.movingTruckMarker.setLatLng([currentLat, currentLng]);
                    }}
                    if (progress < 1) {{
                        requestAnimationFrame(step);
                    }} else {{
                        window.movingTruckMarker.bindPopup("<b>Goods Transferred / Arrived!</b>").openPopup();
                    }}
                }}
                requestAnimationFrame(step);
            }}

            // 3. Fetch True Road Polyline from OSRM (if no valid truck found)
            function fetchAndDrawRoute(animationColors) {{
                if (mapInstance) {{
                    var fromCoords = [locCoords[fromPt][1], locCoords[fromPt][0]];
                    var toCoords = [locCoords[toPt][1], locCoords[toPt][0]];
                    
                    startMarker = L.marker(fromCoords, {{title: fromPt}}).bindPopup("<b>From: </b>" + fromPt).addTo(mapInstance);
                    endMarker = L.marker(toCoords, {{title: toPt}}).bindPopup("<b>To: </b>" + toPt).addTo(mapInstance);
                    
                    var osrmUrl = "https://router.project-osrm.org/route/v1/driving/" + 
                                  fromCoords[1] + "," + fromCoords[0] + ";" + 
                                  toCoords[1] + "," + toCoords[0] + "?overview=full&geometries=geojson";
                                  
                    fetch(osrmUrl)
                        .then(response => response.json())
                        .then(data => {{
                            if (data.code === "Ok") {{
                                var geojsonRoute = data.routes[0].geometry;
                                customLine = L.geoJSON(geojsonRoute, {{
                                    style: function (feature) {{
                                        return {{color: 'black', weight: 4, dashArray: '10, 10'}};
                                    }}
                                }}).addTo(mapInstance);
                                mapInstance.fitBounds(customLine.getBounds(), {{padding: [50, 50]}});
                                var latlngs = geojsonRoute.coordinates.map(function(c) {{ return [c[1], c[0]]; }});
                                animateTruckAlong(latlngs, animationColors);
                            }} else {{
                                customLine = L.polyline([fromCoords, toCoords], {{color: 'black', dashArray: '10, 10', weight: 3}}).addTo(mapInstance);
                                mapInstance.fitBounds([fromCoords, toCoords], {{padding: [50, 50]}});
                                animateTruckAlong([fromCoords, toCoords], animationColors);
                            }}
                        }})
                        .catch(error => {{
                            customLine = L.polyline([fromCoords, toCoords], {{color: 'black', dashArray: '10, 10', weight: 3}}).addTo(mapInstance);
                            mapInstance.fitBounds([fromCoords, toCoords], {{padding: [50, 50]}});
                            animateTruckAlong([fromCoords, toCoords], animationColors);
                        }});
                }}
            }}

            // 4. Check if there's a delivery truck visiting both points
            var validVehicles = [];
            var truckPathsStr = "";
            var singleTruckAnimationColors = [];
            var singleTruckAnimationRoute = [];
            for (var i = 0; i < routeData.length; i++) {{
                var locs = routeData[i].locations.map(function(l) {{ return l.name; }});
                var fromIdx = locs.indexOf(fromPt);
                var toIdx = locs.indexOf(toPt);
                var color = routeData[i].color;
                if (fromIdx !== -1 && toIdx !== -1) {{
                    validVehicles.push("<span style='color:" + color + "; font-weight:bold;'>Truck " + routeData[i].vehicle + "</span>");
                    
                    // Show this specific truck layer
                    var layer = window[routeData[i].layer_id];
                    if (layer && mapInstance) {{
                        mapInstance.addLayer(layer);
                    }}
                    
                    // Keep the valid route to animate it later
                    if (singleTruckAnimationRoute.length === 0) {{
                        var startIndex = Math.min(fromIdx, toIdx);
                        var endIndex = Math.max(fromIdx, toIdx);
                        for(var k=startIndex; k<=endIndex; k++) {{
                            singleTruckAnimationRoute.push([routeData[i].locations[k].lat, routeData[i].locations[k].lon]);
                        }}
                        if (fromIdx > toIdx) singleTruckAnimationRoute.reverse();
                        singleTruckAnimationColors.push(color);
                    }}
                    
                    // Verbally display the whole path the truck makes
                    var pathTaken = locs.join(' ➔ ');
                    var orderText = fromIdx < toIdx ? "" : " <span style='color:orange;'>(Reverse Order)</span>";
                    truckPathsStr += "<div style='margin-top:5px; padding:5px; background:#f8f9fa; border:1px solid #ddd; border-radius:4px; max-height: 150px; overflow-y: auto;'>";
                    truckPathsStr += "<strong style='color:" + color + "'>Truck " + routeData[i].vehicle + "</strong> full route" + orderText + ":<br/>";
                    truckPathsStr += "<span style='color:green;'>" + pathTaken + "</span></div>";
                }}
            }}
            
            if (validVehicles.length > 0) {{
                msgContent += "<strong>Delivery Network:</strong><br/>";
                msgContent += "<span>Served by: " + validVehicles.join(', ') + "</span><br/>";
                msgContent += truckPathsStr;
                
                // Fit bounds to the selected points even if we don't draw the custom line
                if (mapInstance) {{
                    var fromCoords = [locCoords[fromPt][1], locCoords[fromPt][0]];
                    var toCoords = [locCoords[toPt][1], locCoords[toPt][0]];
                    mapInstance.fitBounds([fromCoords, toCoords], {{padding: [50, 50]}});
                    if (singleTruckAnimationRoute.length > 0) {{
                        animateTruckAlong(singleTruckAnimationRoute, singleTruckAnimationColors);
                    }}
                }}
            }} else {{
                // Find all trucks serving fromPt and toPt
                var fromTrucks = [];
                var toTrucks = [];
                for (var i = 0; i < routeData.length; i++) {{
                    var locs = routeData[i].locations.map(function(l) {{ return l.name; }});
                    if (locs.indexOf(fromPt) !== -1) fromTrucks.push(routeData[i]);
                    if (locs.indexOf(toPt) !== -1) toTrucks.push(routeData[i]);
                }}

                function distance(p1, p2) {{
                    var lat1 = p1[0], lon1 = p1[1], lat2 = p2[0], lon2 = p2[1];
                    var p = 0.017453292519943295;
                    var c = Math.cos;
                    var a = 0.5 - c((lat2 - lat1) * p)/2 + 
                            c(lat1 * p) * c(lat2 * p) * 
                            (1 - c((lon2 - lon1) * p))/2;
                    return 12742 * Math.asin(Math.sqrt(a));
                }}

                var bestDist = Infinity;
                var bestFromNode = null;
                var bestToNode = null;
                var bestFromTruck = null;
                var bestToTruck = null;
                
                for (var i = 0; i < fromTrucks.length; i++) {{
                    for (var j = 0; j < toTrucks.length; j++) {{
                        var tFrom = fromTrucks[i];
                        var tTo = toTrucks[j];
                        for (var n1 of tFrom.locations) {{
                            for (var n2 of tTo.locations) {{
                                var d = distance([n1.lat, n1.lon], [n2.lat, n2.lon]);
                                if (d < bestDist) {{
                                    bestDist = d;
                                    bestFromNode = n1;
                                    bestToNode = n2;
                                    bestFromTruck = tFrom;
                                    bestToTruck = tTo;
                                }}
                            }}
                        }}
                    }}
                }}
                
                function extractPath(truck, startName, endName) {{
                    var names = truck.locations.map(l => l.name);
                    var idx1 = names.indexOf(startName);
                    var idx2 = names.indexOf(endName);
                    var start = Math.min(idx1, idx2);
                    var end = Math.max(idx1, idx2);
                    var path = [];
                    for(var i=start; i<=end; i++) {{
                        path.push([truck.locations[i].lat, truck.locations[i].lon]);
                    }}
                    if (idx1 > idx2) path.reverse();
                    return path;
                }}

                var path1 = extractPath(bestFromTruck, fromPt, bestFromNode.name);
                var path2 = extractPath(bestToTruck, bestToNode.name, toPt);
                
                var osrmUrl = "https://router.project-osrm.org/route/v1/driving/" + 
                              bestFromNode.lon + "," + bestFromNode.lat + ";" + 
                              bestToNode.lon + "," + bestToNode.lat + "?overview=full&geometries=geojson";
                              
                msgContent += "<strong>Delivery Network:</strong><br/>";
                msgContent += "<span style='color: #28a745;'><strong>✓ Optimal Multi-Hop Relay Found</strong></span><br/>";
                msgContent += "<div style='font-size:0.9em; padding:5px; background:#f8f9fa; border:1px solid #ddd; border-radius:4px;'>";
                msgContent += "<span style='color:" + bestFromTruck.color + "; font-weight:bold;'>Truck " + bestFromTruck.vehicle + "</span> (" + fromPt + " ➔ " + bestFromNode.name + ")<br/>";
                msgContent += "⬇️ <i>3rd-Party Courier Link (Distance: " + bestDist.toFixed(1) + " km)</i><br/>";
                msgContent += "<span style='color:" + bestToTruck.color + "; font-weight:bold;'>Truck " + bestToTruck.vehicle + "</span> (" + bestToNode.name + " ➔ " + toPt + ")</div>";
                
                startMarker = L.marker([locCoords[fromPt][1], locCoords[fromPt][0]], {{title: fromPt}}).bindPopup("<b>From: </b>" + fromPt).addTo(mapInstance);
                endMarker = L.marker([locCoords[toPt][1], locCoords[toPt][0]], {{title: toPt}}).bindPopup("<b>To: </b>" + toPt).addTo(mapInstance);
                
                fetch(osrmUrl)
                    .then(response => response.json())
                    .then(data => {{
                        var transferCoords = [[bestFromNode.lat, bestFromNode.lon], [bestToNode.lat, bestToNode.lon]];
                        if (data.code === "Ok") {{
                            transferCoords = data.routes[0].geometry.coordinates.map(c => [c[1], c[0]]);
                        }}
                        
                        var fullPath = path1.concat(transferCoords).concat(path2);
                        
                        var tMarker1 = L.marker([bestFromNode.lat, bestFromNode.lon]).bindPopup("<b>Transfer Exit: </b>" + bestFromNode.name);
                        var tMarker2 = L.marker([bestToNode.lat, bestToNode.lon]).bindPopup("<b>Transfer Entry: </b>" + bestToNode.name);
                        
                        customLine = L.featureGroup([
                            L.polyline(path1, {{color: bestFromTruck.color, weight: 6, opacity: 0.8}}),
                            L.polyline(transferCoords, {{color: '#333333', weight: 4, dashArray: '10, 10'}}),
                            L.polyline(path2, {{color: bestToTruck.color, weight: 6, opacity: 0.8}}),
                            tMarker1,
                            tMarker2
                        ]).addTo(mapInstance);
                        
                        mapInstance.fitBounds(customLine.getBounds(), {{padding: [50, 50]}});
                        animateTruckAlong(fullPath, [bestFromTruck.color, '#333333', bestToTruck.color]);
                    }})
                    .catch(error => {{
                        var transferCoords = [[bestFromNode.lat, bestFromNode.lon], [bestToNode.lat, bestToNode.lon]];
                        var fullPath = path1.concat(transferCoords).concat(path2);
                        customLine = L.featureGroup([
                            L.polyline(path1, {{color: bestFromTruck.color, weight: 6}}),
                            L.polyline(transferCoords, {{color: '#333333', weight: 4, dashArray: '10, 10'}}),
                            L.polyline(path2, {{color: bestToTruck.color, weight: 6}})
                        ]).addTo(mapInstance);
                        mapInstance.fitBounds(customLine.getBounds(), {{padding: [50, 50]}});
                        animateTruckAlong(fullPath, [bestFromTruck.color, '#333333', bestToTruck.color]);
                    }});
            }}
            
            if (msgContent !== "") {{
                msg.innerHTML = "<div style='background: white; padding: 12px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); pointer-events: auto; max-width: 300px;'>" + msgContent + "</div>";
            }} else {{
                msg.innerHTML = "";
            }}
        }}
        
        function resetFilter() {{
            document.getElementById('filter_from').value = "";
            document.getElementById('filter_to').value = "";
            document.getElementById('filter_msg').innerHTML = "";
            
            if (customLine && mapInstance) {{
                mapInstance.removeLayer(customLine);
                customLine = null;
            }}
            if (startMarker && mapInstance) {{
                mapInstance.removeLayer(startMarker);
                startMarker = null;
            }}
            if (endMarker && mapInstance) {{
                mapInstance.removeLayer(endMarker);
                endMarker = null;
            }}
            
            // Show all truck layers again
            if (mapInstance) {{
                for (var i = 0; i < routeData.length; i++) {{
                    var layer = window[routeData[i].layer_id];
                    if (layer && !mapInstance.hasLayer(layer)) {{
                        mapInstance.addLayer(layer);
                    }}
                }}
                mapInstance.setView([7.8731, 80.7718], 8);
            }}
        function initAndApply() {{
            for (var key in window) {{
                if (window[key] && window[key] instanceof L.Map) {{
                    mapInstance = window[key];
                    break;
                }}
            }}
            
            if (mapInstance) {{
                // AUTOMATIC URL PARAMETER PARSING
                var urlParams = new URLSearchParams(window.location.search);
                var urlFrom = urlParams.get('from');
                var urlTo = urlParams.get('to');
                if (urlFrom && urlTo) {{
                    applyFilter(urlFrom, urlTo);
                }}
            }} else {{
                setTimeout(initAndApply, 200); // Check again in 200ms
            }}
        }}
        initAndApply();
        
        window.addEventListener('message', function(event) {{
            if (event.data.action === 'analyze') {{
                applyFilter(event.data.from, event.data.to);
            }} else if (event.data.action === 'reset') {{
                resetFilter();
            }}
        }});
    </script>
    """
    
    m.get_root().html.add_child(folium.Element(overlay_html))
    
    # Save map
    map_path = os.path.join(os.path.dirname(__file__), "optimization_map.html")
    m.save(map_path)
    print(f"\n[SUCCESS] Interactive Geographic Map saved to: {map_path}")
    print("Open this HTML file in your browser for the presentation!")

if __name__ == '__main__':
    solve_routing()
