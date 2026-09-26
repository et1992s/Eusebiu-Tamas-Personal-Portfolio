import os
from typing import Any, Optional
import pandas as pd

# Import all textbook graph implementations
from app.services.tube.adjacency_list_graph import AdjacencyListGraph
from app.services.tube.dijkstra import dijkstra
from app.services.tube.bellman_ford import bellman_ford
from app.services.tube.mst import kruskal


class TubeEngineManager:
    def __init__(self):
        # Resolve path to the clean data folder
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.file_path: str = os.path.join(base_dir, "data", "london_underground_data.xlsx")
        
        # State containers
        self.stations_to_int: dict[str, int] = {}
        self.int_to_stations: dict[int, str] = {}
        self.connections: list[tuple[str, str, int]] = []
        
        # Explicit Optional types to satisfy Pylance initialization rules
        self.filtered_dataset: Optional[pd.DataFrame] = None
        self.graph_time: Optional[AdjacencyListGraph] = None
        self.graph_stops: Optional[AdjacencyListGraph] = None
        
        # Auto-initialization state on bootstrap
        self._bootstrap_engine()

    def _bootstrap_engine(self) -> None:
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"Missing critical transit asset at: {self.file_path}")

        df = pd.read_excel(self.file_path)
        df['Line'] = df['Line'].str.strip()
        df['Station'] = df['Station'].str.strip()
        df['Connection'] = df['Connection'].str.strip()
        self.filtered_dataset = df

        # Filter for stations without connections to establish unique IDs
        base_stations = df[df["Connection"].isna() & df['Time'].isna()]
        
        idx = 0
        for _, row in base_stations.iterrows():
            station_name = str(row.iloc[1]).upper()
            if station_name not in self.stations_to_int:
                self.stations_to_int[station_name] = idx
                self.int_to_stations[idx] = station_name
                idx += 1

        # Extracting real connections
        active_connections = df[df["Connection"].notna() & df['Time'].notna()]
        for _, row in active_connections.iterrows():
            self.connections.append((str(row.iloc[1]).upper(), str(row.iloc[2]).upper(), int(row.iloc[3])))

        # Sorting to ensure that the lowest transit times will load into the structural matrices
        self.connections = sorted(self.connections, key=lambda c: c[2])

        # Instantiating the structural CLRS Adjacency Graphs
        v_count = len(self.stations_to_int)
        self.graph_time = AdjacencyListGraph(v_count, directed=False, weighted=True)
        self.graph_stops = AdjacencyListGraph(v_count, directed=False, weighted=True)

        for src_name, dest_name, travel_time in self.connections:
            src_id = self.stations_to_int[src_name]
            dest_id = self.stations_to_int[dest_name]
            try:
                self.graph_time.insert_edge(src_id, dest_id, travel_time)
                self.graph_stops.insert_edge(src_id, dest_id, 1)
            except RuntimeError:
                continue

    def backtracking(self, starting_point: int, destination: int, distance: list[Any], pi: list[Any]) -> tuple[list[str], Any]:
        """Preserves custom array backtracking logic, returning named nodes."""
        shortest_route_ids = []
        journey_metric = distance[destination]
        curr = destination
        
        while True:
            if pi[curr] is not None:
                shortest_route_ids.append(curr)
                curr = pi[curr]
            else:
                shortest_route_ids.append(starting_point)
                break
                
        shortest_route_ids = shortest_route_ids[::-1]
        # Converting the IDs back to the actual printable station names
        named_route = [self.int_to_stations[sid] for sid in shortest_route_ids]
        return named_route, journey_metric

    def compute_dijkstra_route(self, start_name: str, dest_name: str, minimize_stops: bool = False) -> tuple[list[str], Any]:
        """Running the Dijkstra's algorithm from start to destination station."""
        start_clean = start_name.strip().upper()
        dest_clean = dest_name.strip().upper()

        if start_clean not in self.stations_to_int or dest_clean not in self.stations_to_int:
            raise ValueError("One or both station names do not exist in the London Underground database.")

        graph = self.graph_stops if minimize_stops else self.graph_time
        if graph is None:
            raise RuntimeError("Engine graphs are uninitialized.")

        start_idx = self.stations_to_int[start_clean]
        dest_idx = self.stations_to_int[dest_clean]

        # Calling the imported textbook execution
        d, pi = dijkstra(graph, start_idx)
        
        return self.backtracking(start_idx, dest_idx, d, pi)

    def compute_bellman_ford_route(self, start_name: str, dest_name: str, minimize_stops: bool = False) -> tuple[list[str], Any, bool]:
        """Running the Bellman-Ford algorithm from start to destination station. Returns (route, cost, and if it has_negative_cycle)."""
        start_clean = start_name.strip().upper()
        dest_clean = dest_name.strip().upper()

        if start_clean not in self.stations_to_int or dest_clean not in self.stations_to_int:
            raise ValueError("One or both station names do not exist in the London Underground database.")

        graph = self.graph_stops if minimize_stops else self.graph_time
        if graph is None:
            raise RuntimeError("Engine graphs are uninitialized.")

        start_idx = self.stations_to_int[start_clean]
        dest_idx = self.stations_to_int[dest_clean]

        # Calling the imported textbook execution
        d, pi, cycle = bellman_ford(graph, start_idx)
        
        route, metric = self.backtracking(start_idx, dest_idx, d, pi)
        return route, metric, cycle

    def compute_closures(self) -> list[dict[str, Any]]:
        """Executing Task 4 Kruskal MST isolation logic."""
        if self.graph_time is None or self.filtered_dataset is None:
            return []

        mst_time_graph = kruskal(self.graph_time)
        
        full_edges = set(self.graph_time.get_edge_list())
        mst_edges = set(mst_time_graph.get_edge_list())
        deleted_edges = full_edges.difference(mst_edges)
        
        closures = []
        for u, v in deleted_edges:
            st_a = self.int_to_stations[u]
            st_b = self.int_to_stations[v]
            
            line_match = "UNKNOWN"
            for _, row in self.filtered_dataset.iterrows():
                row_st = str(row['Station']).upper()
                row_conn = str(row['Connection']).upper()
                if (row_st == st_a and row_conn == st_b) or (row_st == st_b and row_conn == st_a):
                    line_match = str(row['Line']).upper()
                    break
            
            closures.append({
                "line": line_match,
                "station_a": st_a,
                "station_b": st_b
            })
        return closures


# Instantiating a single engine context to share across the API processes
tube_engine = TubeEngineManager()