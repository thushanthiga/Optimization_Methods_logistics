# Advanced FMCG Logistics Optimization in Sri Lanka
**Multi-Depot Heterogeneous Vehicle Routing Problem with Time Windows (MD-HVRPTW)**

## 1. Problem Statement
This project models a massive, real-world supply chain for Fast-Moving Consumer Goods (FMCG) distribution across Sri Lanka. The model evaluates a **Multi-Depot Heterogeneous Fleet** network spanning 75 real-world locations to optimize distribution routes and minimize transit times.

Goods are collected at 5 major National/Regional Distribution Hubs (Colombo, Kandy, Galle, Jaffna, Trincomalee) and must be distributed to 70 major towns and cities across the island. 

**Advanced Constraints Introduced:**
1. **Multi-Depot (MD):** Trucks originate from 5 completely separate starting and ending hubs across the country.
2. **Heterogeneous Fleet (H):** The fleet consists of different vehicle types (25-ton heavy trucks and 15-ton standard trucks) with different capacities.
3. **Time Windows (TW):** Regional markets and supermarkets require deliveries within specific hours.
4. **Real-World Geographic Data:** Uses actual coordinates from 75 Sri Lankan cities and a 75x75 API-driven distance/duration matrix (5,625 distance pairs) fetched directly from the OpenStreetMap (OSRM) engine.

## 2. Methodology Split
### Part A: Exact Method (Person 1 - Highly Mathematical)
*   **Technique:** Mixed-Integer Linear Programming (MILP).
*   **Implementation:** Google OR-Tools.
*   **Complexity:** Formulating an Exact model for a 75-node MD-HVRPTW involves multi-dimensional variables. It mathematically links depot origins, tracks time dimension variables across 5,625 possible paths, and balances heterogeneous vehicle usage. 
*   **Output:** Generates the mathematical lower-bound cost and an interactive geospatial map of the optimal routes.

### Part B: Metaheuristic Method (Person 2)
*   **Technique:** Genetic Algorithm (GA).
*   **Implementation:** DEAP Framework.
*   **Complexity:** Standard GAs fail on Multi-Depot with Time Windows. The implementation utilizes a complex chromosome permutation representation and custom decoding operators to handle multiple depots and heterogeneous trucks across 70 drop-off points.

## 3. Dataset Details (Massive Scale)
*   **Depots (5):** Colombo, Kandy, Galle, Jaffna, Trincomalee.
*   **Demand Nodes (70):** 70 major population centers across Sri Lanka (Ratnapura, Anuradhapura, Batticaloa, etc.).
*   **Demand Generation:** Demand is deterministically mapped as a proxy of location scale and geographic distribution.
*   **Distance/Time Matrix:** Extracted live via the **OSRM Public Routing API** using exact GPS coordinates and cached in a JSON matrix.
*   **Visualizations:** Programmatic generation of `folium` interactive HTML maps showing the flow of goods across the island.

## 4. Mathematical Formulation
**Sets:** 
* $D$: Set of Depots (Size: 5)
* $C$: Set of Customers (Markets) (Size: 70)
* $N$: Set of all nodes ($D \cup C$) (Size: 75)
* $K$: Set of heterogeneous vehicles (Size: 30)

**Parameters:** 
* $d_{ij}$: Distance from node $i$ to $j$
* $t_{ij}$: Travel time from node $i$ to $j$
* $q_i$: Demand at market $i$
* $Q_k$: Capacity of vehicle $k$
* $C_k$: Fixed operating cost of vehicle $k$
* $[e_i, l_i]$: Time window for market $i$

**Decision Variables:** 
* $x_{ijk} \in \{0, 1\}$: 1 if vehicle $k$ travels directly from $i$ to $j$.
* $w_{ik} \ge 0$: Arrival time of vehicle $k$ at node $i$.

**Objective (Minimize Total Cost & Fleet Usage):** 
$\text{Min} \sum_{k \in K} \sum_{i \in N} \sum_{j \in N} (d_{ij}) x_{ijk}$

**Key Advanced Constraints:**
1. $\sum_{i \in C} q_i \sum_{j \in N} x_{ijk} \le Q_k \quad \forall k \in K$ *(Heterogeneous Capacity)*
2. $\sum_{j \in C} x_{djk} \le \text{MaxVehicles}_d \quad \forall d \in D$ *(Depot Vehicle Limits)*
3. $w_{ik} + t_{ij} - w_{jk} \le (1 - x_{ijk}) M$ *(Time tracking & Subtour Elimination)*
