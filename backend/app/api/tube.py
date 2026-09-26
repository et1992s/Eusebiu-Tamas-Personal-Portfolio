from fastapi import APIRouter, HTTPException, Query
from app.services.tube.graph_builder import tube_engine
from app.services.tube.dijkstra import dijkstra
from app.services.tube.bellman_ford import bellman_ford

router = APIRouter(prefix="/tube", tags=["London Underground Transit Engine"])

@router.get("/stations")
async def get_stations():
    """ Exposing unique stations for selection lists """
    return {
        "count": len(tube_engine.stations_to_int),
        "stations": sorted(list(tube_engine.stations_to_int.keys()))
    }

@router.get("/route")
async def find_route(
    start: str = Query(..., description="Starting station name (e.g. BAKER STREET)"),
    end: str = Query(..., description="Destination station name (e.g. KINGS CROSS)"),
    routing_type: str = Query("time", description="Optimize by: 'time' or 'stops'"),
    algorithm: str = Query("dijkstra", description="Algorithm to run: 'dijkstra' or 'bellman_ford'")
):
    """ Executing real-time routing simulations using the referenced algorithms textbook """
    start_clean = start.strip().upper()
    end_clean = end.strip().upper()

    if start_clean not in tube_engine.stations_to_int or end_clean not in tube_engine.stations_to_int:
        raise HTTPException(status_code=400, detail="Invalid starting or destination station name.")

    start_id = tube_engine.stations_to_int[start_clean]
    end_id = tube_engine.stations_to_int[end_clean]
    
    # Target correct graph state based on user choice
    graph = tube_engine.graph_time if routing_type == "time" else tube_engine.graph_stops

    # Run selected algorithm execution loops
    if algorithm == "dijkstra":
        d, pi = dijkstra(graph, start_id)
    elif algorithm == "bellman_ford":
        d, pi, cycle = bellman_ford(graph, start_id)
        if not cycle:
            raise HTTPException(status_code=422, detail="The graph contains a negative cycle. Route aborted.")
    else:
        raise HTTPException(status_code=400, detail="Unsupported routing algorithm.")

    # Execute your backtracking array matrix
    route, metric = tube_engine.backtracking(start_id, end_id, d, pi)

    return {
        "origin": start_clean,
        "destination": end_clean,
        "algorithm_used": algorithm,
        "optimized_by": routing_type,
        "total_stops": len(route) - 1,
        "journey_metric": metric,
        "route_sequence": route
    }

@router.get("/closures")
async def get_mst_closures():
    """ Task 4a: Calculating the network optimization closures via Kruskal's Minimum Spanning Tree """
    try:
        deletions = tube_engine.compute_closures()
        return {
            "total_recommended_closures": len(deletions),
            "closures": deletions
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"MST Calculation failed: {str(e)}")