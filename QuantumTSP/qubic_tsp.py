# GRAF NIEPEŁNY TSP - LISTA ODWIEDZONYCH
cost = [
    [0, 20, 30, 10, 11, 15, 25, 19],
    [20, 0, 16, 22, 25, 18, 21, 13],
    [30, 16, 0, 28, 12, 32, 14, 24],
    [10, 22, 28, 0, 15, 19, 23, 18],
    [11, 25, 12, 15, 0, 27, 17, 20],
    [15, 18, 32, 19, 27, 0, 26, 22],
    [25, 21, 14, 23, 17, 26, 0, 29],
    [19, 13, 24, 18, 20, 22, 29, 0]
]
n = len(cost)
qubits = [None, None, None, None, None, None]
def tsp_backtrack(visited, path, current_cost):
    if len(visited) == n:  # Wszystkie miasta!
        start = path[0]
        last = path[-1]
        if cost[last][start] is not None:
            return current_cost + cost[last][start], path
        return float('inf'), None
    
    best_cost = float('inf')
    best_path = None
    last = path[-1]
    
    for next_city in range(n):
        if next_city not in visited and cost[last][next_city] is not None:
            new_visited = visited + [next_city]  # DODAJ do listy
            new_path = path + [next_city]
            new_cost = current_cost + cost[last][next_city]
            # print("#",cost[last][next_city])
            
            cost_so_far, path_so_far = tsp_backtrack(new_visited, new_path, new_cost)
            if cost_so_far < best_cost:
                best_cost = cost_so_far
                best_path = path_so_far
    
    return best_cost, best_path

# ROZWIĄZANIE
best_cost = float('inf')
best_path = None
for start in range(0,n):
    cost_val, path = tsp_backtrack([start], [start], 0)
    print("stating from", start) 
    if cost_val < best_cost:
        best_cost = cost_val
        best_path = path

print(f"Best route: {best_path} -> {best_path[0]}, Cost: {best_cost}")
