import React, { useEffect, useState, useMemo } from 'react';
import { tubeApi } from '../../services/api';
import tubeSchematic from '../../data/tube-schematic.json';
import svgStations from '../../data/svg-stations-extracted.json';
// Adjust this path to wherever tfl-map.svg actually lives.
// If it's in `public/`, just use "/tfl-map.svg".
import tflMapUrl from '../../assets/tfl-map.svg';

// viewBox shared by tfl-map.svg and tube-schematic.json
const VIEWBOX = '-40.5 -120.5 2500 1320';

const normalize = (name) =>
  String(name || '').toUpperCase().replace(/[^A-Z0-9]/g, '');

/* ------------------------------------------------------------------ */
/* Station index from svg-stations-extracted.json                     */
/* ------------------------------------------------------------------ */
const STATION_INDEX = (() => {
  const map = new Map();
  for (const [id, data] of Object.entries(svgStations)) {
    if (!data?.coordinate) continue;
    const key = normalize(id);
    if (!map.has(key)) {
      map.set(key, {
        id,
        coordinate: data.coordinate,
        lines: data.lines || [],
      });
    }
  }
  return map;
})();

function findStation(rawName) {
  const key = normalize(rawName);
  if (!key) return null;
  if (STATION_INDEX.has(key)) return STATION_INDEX.get(key);
  // Fallback: allow the suffixed variants used in the extracted file
  // (e.g. "Barons_Court_district", "Canary_Wharf_elizabeth").
  for (const [k, v] of STATION_INDEX) {
    if (k.startsWith(key) && k.length - key.length <= 14) return v;
  }
  return null;
}

/* ------------------------------------------------------------------ */
/* Small geometry helpers                                             */
/* ------------------------------------------------------------------ */
const dist = (a, b) => Math.hypot(b[0] - a[0], b[1] - a[1]);

function polylineLengths(points) {
  const lens = [0];
  for (let i = 1; i < points.length; i++) {
    lens.push(lens[i - 1] + dist(points[i - 1], points[i]));
  }
  return lens;
}

function projectPointOnPolyline(point, polyline) {
  const lens = polylineLengths(polyline);
  let best = null;
  for (let i = 1; i < polyline.length; i++) {
    const a = polyline[i - 1];
    const b = polyline[i];
    const dx = b[0] - a[0];
    const dy = b[1] - a[1];
    const segSq = dx * dx + dy * dy;
    let t = segSq === 0
      ? 0
      : ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / segSq;
    t = Math.max(0, Math.min(1, t));
    const px = a[0] + t * dx;
    const py = a[1] + t * dy;
    const d = Math.hypot(point[0] - px, point[1] - py);
    const arc = lens[i - 1] + t * (lens[i] - lens[i - 1]);
    if (!best || d < best.distance) {
      best = { distance: d, arcDistance: arc, point: [px, py] };
    }
  }
  return best;
}

function pointAtArc(polyline, lens, arc) {
  if (arc <= 0) return [...polyline[0]];
  const total = lens[lens.length - 1];
  if (arc >= total) return [...polyline[polyline.length - 1]];
  for (let i = 1; i < polyline.length; i++) {
    if (lens[i] >= arc) {
      const seg = lens[i] - lens[i - 1];
      const t = seg === 0 ? 0 : (arc - lens[i - 1]) / seg;
      return [
        polyline[i - 1][0] + t * (polyline[i][0] - polyline[i - 1][0]),
        polyline[i - 1][1] + t * (polyline[i][1] - polyline[i - 1][1]),
      ];
    }
  }
  return [...polyline[polyline.length - 1]];
}

function extractSegment(polyline, arcStart, arcEnd) {
  const lens = polylineLengths(polyline);
  const s = Math.min(arcStart, arcEnd);
  const e = Math.max(arcStart, arcEnd);
  const pts = [pointAtArc(polyline, lens, s)];
  for (let i = 0; i < polyline.length; i++) {
    if (lens[i] > s + 0.5 && lens[i] < e - 0.5) pts.push(polyline[i]);
  }
  pts.push(pointAtArc(polyline, lens, e));
  if (arcStart > arcEnd) pts.reverse();
  return pts;
}

/* ------------------------------------------------------------------ */
/* Route geometry: for each consecutive pair, pick the schematic      */
/* branch whose arc-distance between the two projections is smallest. */
/* ------------------------------------------------------------------ */
const MAX_MATCH_DISTANCE = 40; // pixels

function buildRouteGeometry(routeStations) {
  const segments = [];
  const stationPoints = {};

  for (let i = 0; i < routeStations.length - 1; i++) {
    const rawA = typeof routeStations[i] === 'string'
      ? routeStations[i]
      : routeStations[i]?.station ?? routeStations[i]?.name;
    const rawB = typeof routeStations[i + 1] === 'string'
      ? routeStations[i + 1]
      : routeStations[i + 1]?.station ?? routeStations[i + 1]?.name;

    const a = findStation(rawA);
    const b = findStation(rawB);
    if (!a || !b) continue;

    const keyA = normalize(rawA);
    const keyB = normalize(rawB);

    let best = null;
    for (const [lineName, polylines] of Object.entries(tubeSchematic)) {
      for (let bi = 0; bi < polylines.length; bi++) {
        const poly = polylines[bi];
        if (poly.length < 2) continue;
        const pa = projectPointOnPolyline(a.coordinate, poly);
        const pb = projectPointOnPolyline(b.coordinate, poly);
        if (!pa || !pb) continue;
        if (pa.distance > MAX_MATCH_DISTANCE) continue;
        if (pb.distance > MAX_MATCH_DISTANCE) continue;
        const arcSpan = Math.abs(pa.arcDistance - pb.arcDistance);
        if (!best || arcSpan < best.arcSpan) {
          best = { lineName, poly, pa, pb, arcSpan };
        }
      }
    }

    if (best && best.arcSpan > 0.5) {
      const pts = extractSegment(best.poly, best.pa.arcDistance, best.pb.arcDistance);
      if (pts.length >= 2) {
        segments.push({ points: pts, traced: true, line: best.lineName });
      }
    }

    if (!stationPoints[keyA]) stationPoints[keyA] = a.coordinate;
    stationPoints[keyB] = b.coordinate;
  }

  return { segments, stationPoints };
}

/* ------------------------------------------------------------------ */
/* Component                                                          */
/* ------------------------------------------------------------------ */
const TubeRoutePanel = () => {
  const [stations, setStations] = useState([]);
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [routingType, setRoutingType] = useState('time');
  const [algorithm, setAlgorithm] = useState('dijkstra');
  const [route, setRoute] = useState(null);
  const [loadingStations, setLoadingStations] = useState(true);
  const [loadingRoute, setLoadingRoute] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    (async () => {
      try {
        const data = await tubeApi.getStations();
        setStations(data.stations || []);
      } catch {
        setError('Unable to load stations.');
      } finally {
        setLoadingStations(false);
      }
    })();
  }, []);

  const handleFindRoute = async () => {
    if (!start || !end) return setError('Pick both stations.');
    if (start === end) return setError('Origin and destination must differ.');
    setLoadingRoute(true);
    setError('');
    setRoute(null);

    try {
      const data = await tubeApi.findRoute({ start, end, routingType, algorithm });
      setRoute(data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Unable to calculate the route.');
    } finally {
      setLoadingRoute(false);
    }
  };

  const { segments, stationPoints } = useMemo(() => {
    if (!route?.route) return { segments: [], stationPoints: {} };
    return buildRouteGeometry(route.route);
  }, [route]);

  return (
    <section className="tube-route-panel">
      <div className="tube-route-header">
        <div>
          <span className="section-kicker">GRAPH ANALYSIS</span>
          <h2>London Underground</h2>
          <p>Shortest-path routing using classical graph algorithms.</p>
        </div>
      </div>

      <div className="tube-route-controls">
        <label>
          <span>From</span>
          <select
            value={start}
            onChange={(e) => setStart(e.target.value)}
            disabled={loadingStations}
          >
            <option value="">Select station</option>
            {stations.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </label>
        <label>
          <span>To</span>
          <select
            value={end}
            onChange={(e) => setEnd(e.target.value)}
            disabled={loadingStations}
          >
            <option value="">Select station</option>
            {stations.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </label>
        <label>
          <span>Optimise by</span>
          <select value={routingType} onChange={(e) => setRoutingType(e.target.value)}>
            <option value="time">Journey time</option>
            <option value="stops">Number of stops</option>
          </select>
        </label>
        <label>
          <span>Algorithm</span>
          <select value={algorithm} onChange={(e) => setAlgorithm(e.target.value)}>
            <option value="dijkstra">Dijkstra</option>
            <option value="bellman_ford">Bellman-Ford</option>
          </select>
        </label>
      </div>

      <button
        type="button"
        className="tube-route-button"
        onClick={handleFindRoute}
        disabled={loadingStations || loadingRoute}
      >
        {loadingRoute ? 'Calculating route...' : 'Find shortest route'}
      </button>

      <div className="tube-schematic-container">
        <img
          src={tflMapUrl}
          alt="London Underground map"
          className="tube-map-image"
          draggable={false}
        />
        <svg
          className="tube-schematic"
          viewBox={VIEWBOX}
          preserveAspectRatio="xMidYMid meet"
          role="img"
          aria-label="Route overlay"
        >
          {route && (
            <>
              {segments.map((seg, i) => (
                <React.Fragment key={`seg-${i}`}>
                  <polyline
                    points={seg.points.map(([x, y]) => `${x},${y}`).join(' ')}
                    fill="none"
                    className="tube-route-highlight-underlay"
                  />
                  <polyline
                    points={seg.points.map(([x, y]) => `${x},${y}`).join(' ')}
                    fill="none"
                    className="tube-route-highlight"
                  />
                </React.Fragment>
              ))}

              {route.route.map((station, index) => {
                const name =
                  typeof station === 'string'
                    ? station
                    : station?.station ?? station?.name;
                const coord = stationPoints[normalize(name)];
                if (!coord) return null;
                const [x, y] = coord;
                return (
                  <g
                    key={`node-${index}`}
                    className="tube-route-node"
                    style={{ animationDelay: `${index * 180}ms` }}
                  >
                    <circle cx={x} cy={y} r="15" className="tube-route-node-outer" />
                    <circle cx={x} cy={y} r="10" className="tube-route-node-inner" />
                  </g>
                );
              })}
            </>
          )}
        </svg>
      </div>

      {error && <div className="tube-route-error">{error}</div>}

      {route && (
        <div className="tube-route-result">
          <div className="tube-route-result-header">
            <div>
              <span className="section-kicker">CALCULATED ROUTE</span>
              <h3>
                {typeof route.route[0] === 'string'
                  ? route.route[0]
                  : route.route[0]?.station}
                {' → '}
                {typeof route.route[route.route.length - 1] === 'string'
                  ? route.route[route.route.length - 1]
                  : route.route[route.route.length - 1]?.station}
              </h3>
            </div>
            <span className="tube-route-algorithm">{route.algorithm}</span>
          </div>
          <div className="tube-route-stats">
            <div><span>Stops</span><strong>{route.route.length - 1}</strong></div>
            <div><span>Minutes</span><strong>{route.total_cost}</strong></div>
            <div>
              <span>Optimised by</span>
              <strong>{route.optimization === 'time' ? 'Journey time' : 'Stops'}</strong>
            </div>
          </div>
          <div className="tube-route-sequence">
            <span>Route sequence</span>
            <div className="tube-route-stations">
              {route.route.map((station, index) => {
                const name =
                  typeof station === 'string'
                    ? station
                    : station?.station ?? station?.name;
                return (
                  <React.Fragment key={`${name}-${index}`}>
                    <span
                      className="tube-route-station"
                      style={{ animationDelay: `${index * 180}ms` }}
                    >
                      <span className="tube-route-station-index">{index + 1}</span>
                      {name}
                    </span>
                    {index < route.route.length - 1 && (
                      <span
                        className="tube-route-arrow"
                        style={{ animationDelay: `${index * 180 + 120}ms` }}
                      >
                        →
                      </span>
                    )}
                  </React.Fragment>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </section>
  );
};

export default TubeRoutePanel;