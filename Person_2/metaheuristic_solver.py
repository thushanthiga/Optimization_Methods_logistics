import random
import folium
import os
import sys
import numpy as np

# Add the parent directory to the path so we can import the shared agri_opt module
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from deap import base, creator, tools, algorithms
from agri_opt.data_model import DATA

MARKET_COUNT = 70 # We have 70 markets (indices 5 to 74)

# --- 2. GENETIC ALGORITHM SETUP (DEAP) ---
# We represent a chromosome as a permutation of 0 to 69.
# We then decode this permutation into vehicle routes by adding 5.

def decode_chromosome(individual):
    """Decodes a permutation of markets into valid vehicle routes."""
    routes = [[] for _ in range(len(DATA['starts']))]
    vehicle_loads = [0] * len(DATA['starts'])
    vehicle_times = [0] * len(DATA['starts'])
    
    current_vehicle = 0
    
    for gene in individual:
        market = gene + 5 # Shift by 5 to get actual location index
        demand = DATA['demands'][market]
        
        # Try to fit the market into the current vehicle
        if current_vehicle < len(DATA['starts']):
            cap = DATA['vehicle_capacities'][current_vehicle]
            if vehicle_loads[current_vehicle] + demand <= cap:
                routes[current_vehicle].append(market)
                vehicle_loads[current_vehicle] += demand
            else:
                # Move to next vehicle
                current_vehicle += 1
                if current_vehicle < len(DATA['starts']):
                    routes[current_vehicle].append(market)
                    vehicle_loads[current_vehicle] += demand
                else:
                    # Out of vehicles! Huge penalty for unserved markets
                    return routes, float('inf')
    return routes, 0 # 0 penalty if all fit

def evaluate_fitness(individual):
    routes, penalty = decode_chromosome(individual)
    if penalty > 0:
        return (penalty,)
        
    total_distance = 0
    for v_idx, route in enumerate(routes):
        if not route: continue
        
        depot = DATA['starts'][v_idx]
        
        # Distance from depot to first market
        dist = DATA['distance_matrix'][depot][route[0]]
        
        # Distance between markets
        for i in range(len(route) - 1):
            dist += DATA['distance_matrix'][route[i]][route[i+1]]
            
        # Distance back to depot
        dist += DATA['distance_matrix'][route[-1]][depot]
        
        total_distance += dist
        
    return (total_distance,)

# DEAP Boilerplate
creator.create("FitnessMin", base.Fitness, weights=(-1.0,))
creator.create("Individual", list, fitness=creator.FitnessMin)

toolbox = base.Toolbox()
toolbox.register("indices", random.sample, range(MARKET_COUNT), MARKET_COUNT)
toolbox.register("individual", tools.initIterate, creator.Individual, toolbox.indices)
toolbox.register("population", tools.initRepeat, list, toolbox.individual)
toolbox.register("evaluate", evaluate_fitness)
toolbox.register("mate", tools.cxPartialyMatched) # PMX Crossover for permutations
toolbox.register("mutate", tools.mutShuffleIndexes, indpb=0.05)
toolbox.register("select", tools.selTournament, tournsize=3)

def run_genetic_algorithm():
    print("Initializing Genetic Algorithm (Metaheuristic) Population...")
    pop = toolbox.population(n=100)
    hof = tools.HallOfFame(1)
    
    stats = tools.Statistics(lambda ind: ind.fitness.values)
    stats.register("min", np.min)
    
    print("Evolving Generations...")
    algorithms.eaSimple(pop, toolbox, cxpb=0.7, mutpb=0.2, ngen=100, stats=stats, halloffame=hof, verbose=True)
    
    best_ind = hof[0]
    best_routes, _ = decode_chromosome(best_ind)
    best_distance = evaluate_fitness(best_ind)[0]
    
    print(f"\n{'='*50}\nGENETIC ALGORITHM OPTIMIZED ROUTES\n{'='*50}")
    for v_idx, route in enumerate(best_routes):
        if not route: continue
        depot_name = DATA['location_names'][DATA['starts'][v_idx]]
        print(f"Vehicle {v_idx} (Cap: {DATA['vehicle_capacities'][v_idx]}kg) starting from {depot_name}:")
        route_names = [DATA['location_names'][m] for m in route]
        print(f"  -> {' -> '.join(route_names)}")
    
    print(f"Total Distance Found via GA: {best_distance} km")

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
        truck_group = folium.FeatureGroup(name=f"Truck {v_idx} (Depot {DATA['location_names'][depot]})")
        
        for node_index in full_route:
            lat, lon = DATA['locations'][node_index][1][1], DATA['locations'][node_index][1][0]
            route_coords.append((lat, lon))
            loc_name = DATA['location_names'][node_index]
            route_locations.append({"name": loc_name, "lat": lat, "lon": lon})
            
            icon_color = 'black' if node_index < 5 else colors[v_idx % len(colors)]
            folium.Marker([lat, lon], popup=loc_name, icon=folium.Icon(color=icon_color)).add_to(truck_group)
            
        folium.PolyLine(route_coords, color=colors[v_idx % len(colors)], weight=2.5, opacity=0.8).add_to(truck_group)
        truck_group.add_to(m)
        
        js_routes.append({"vehicle": v_idx, "locations": route_locations, "layer_id": truck_group.get_name(), "color": colors[v_idx % len(colors)]})
        
    folium.LayerControl().add_to(m)
    
    loc_names = DATA['location_names']
    loc_coords = {name: DATA['locations'][i][1] for i, name in enumerate(loc_names)}
    
    matrix_data = {}
    for i, name1 in enumerate(loc_names):
        matrix_data[name1] = {}
        for j, name2 in enumerate(loc_names):
            matrix_data[name1][name2] = {
                "dist": DATA['distance_matrix'][i][j],
                "time": DATA['time_matrix'][i][j]
            }

    all_locations = sorted(loc_names)
    options_html = "<option value=''>-- Select Point --</option>" + "".join([f"<option value='{loc}'>{loc}</option>" for loc in all_locations])
    
    overlay_html = f"""
    <div style="position: fixed; top: 10px; left: 50px; z-index: 9999; background: white; padding: 15px; border-radius: 8px; box-shadow: 0 0 15px rgba(0,0,0,0.2); width: 320px;">
        <h4 style="margin-top: 0;">Point-to-Point Analysis</h4>
        <label>From Point:</label>
        <select id="filter_from" style="width: 100%; margin-bottom: 10px;">
            {options_html}
        </select>
        <label>To Point:</label>
        <select id="filter_to" style="width: 100%; margin-bottom: 10px;">
            {options_html}
        </select>
        <button onclick="applyFilter()" style="width: 100%; padding: 5px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer;">Analyze Connection</button>
        <button onclick="resetFilter()" style="width: 100%; padding: 5px; margin-top: 5px; background: #6c757d; color: white; border: none; border-radius: 4px; cursor: pointer;">Reset Map</button>
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
        
        setTimeout(function() {{
            for (var key in window) {{
                if (window[key] && window[key] instanceof L.Map) {{
                    mapInstance = window[key];
                    break;
                }}
            }}
        }}, 1000);

        function applyFilter() {{
            var fromPt = document.getElementById('filter_from').value;
            var toPt = document.getElementById('filter_to').value;
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
            
            msg.innerHTML = msgContent;
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
        }}
    </script>
    """
    
    m.get_root().html.add_child(folium.Element(overlay_html))
    
    # Save map
    map_path = os.path.join(os.path.dirname(__file__), "metaheuristic_map.html")
    m.save(map_path)
    print(f"\n[SUCCESS] Interactive Geographic Map saved to: {map_path}")
    print("Open this HTML file in your browser for the presentation!")




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
        truck_group = folium.FeatureGroup(name=f"Truck {v_idx} (Depot {DATA['location_names'][depot]})")
        
        for node_index in full_route:
            lat, lon = DATA['locations'][node_index][1][1], DATA['locations'][node_index][1][0]
            route_coords.append((lat, lon))
            loc_name = DATA['location_names'][node_index]
            route_locations.append({"name": loc_name, "lat": lat, "lon": lon})
            
            icon_color = 'black' if node_index < 5 else colors[v_idx % len(colors)]
            folium.Marker([lat, lon], popup=loc_name, icon=folium.Icon(color=icon_color)).add_to(truck_group)
            
        folium.PolyLine(route_coords, color=colors[v_idx % len(colors)], weight=2.5, opacity=0.8).add_to(truck_group)
        truck_group.add_to(m)
        
        js_routes.append({"vehicle": v_idx, "locations": route_locations, "layer_id": truck_group.get_name(), "color": colors[v_idx % len(colors)]})
        
    folium.LayerControl().add_to(m)
    
    loc_names = DATA['location_names']
    loc_coords = {name: DATA['locations'][i][1] for i, name in enumerate(loc_names)}
    
    matrix_data = {}
    for i, name1 in enumerate(loc_names):
        matrix_data[name1] = {}
        for j, name2 in enumerate(loc_names):
            matrix_data[name1][name2] = {
                "dist": DATA['distance_matrix'][i][j],
                "time": DATA['time_matrix'][i][j]
            }

    all_locations = sorted(loc_names)
    options_html = "<option value=''>-- Select Point --</option>" + "".join([f"<option value='{loc}'>{loc}</option>" for loc in all_locations])
    
    overlay_html = f"""
    <div style="position: fixed; top: 10px; left: 50px; z-index: 9999; background: white; padding: 15px; border-radius: 8px; box-shadow: 0 0 15px rgba(0,0,0,0.2); width: 320px;">
        <h4 style="margin-top: 0;">Point-to-Point Analysis</h4>
        <label>From Point:</label>
        <select id="filter_from" style="width: 100%; margin-bottom: 10px;">
            {options_html}
        </select>
        <label>To Point:</label>
        <select id="filter_to" style="width: 100%; margin-bottom: 10px;">
            {options_html}
        </select>
        <button onclick="applyFilter()" style="width: 100%; padding: 5px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer;">Analyze Connection</button>
        <button onclick="resetFilter()" style="width: 100%; padding: 5px; margin-top: 5px; background: #6c757d; color: white; border: none; border-radius: 4px; cursor: pointer;">Reset Map</button>
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
        
        setTimeout(function() {{
            for (var key in window) {{
                if (window[key] && window[key] instanceof L.Map) {{
                    mapInstance = window[key];
                    break;
                }}
            }}
        }}, 1000);

        function applyFilter() {{
            var fromPt = document.getElementById('filter_from').value;
            var toPt = document.getElementById('filter_to').value;
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
                            window.movingTruckMarker.bindPopup("<b>Transferring Goods...</b>").openPopup();
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
                msgContent += "⬇️ <i>Transfer Gap (Distance: " + bestDist.toFixed(1) + " km)</i><br/>";
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
            
            msg.innerHTML = msgContent;
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
        }}
    </script>
    """
    
    m.get_root().html.add_child(folium.Element(overlay_html))
    
    # Save map
    map_path = os.path.join(os.path.dirname(__file__), "metaheuristic_map.html")
    m.save(map_path)
    print(f"\n[SUCCESS] Interactive Geographic Map saved to: {map_path}")
    print("Open this HTML file in your browser for the presentation!")




if __name__ == "__main__":
    if DATA['distance_matrix'] is not None:
        run_genetic_algorithm()
    else:
        print("Failed to load OSRM data.")
