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

if __name__ == "__main__":
    if DATA['distance_matrix'] is not None:
        run_genetic_algorithm()
    else:
        print("Failed to load OSRM data.")
