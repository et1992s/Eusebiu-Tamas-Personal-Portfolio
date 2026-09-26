const fs = require('fs');
const path = require('path');
const cheerio = require('cheerio');

// Handle all possible export shapes of svg-path-properties across versions
const spp = require('svg-path-properties');
const SvgPathProperties =
  spp.svgPathProperties ||
  spp.SvgPathProperties ||
  spp.default ||
  spp;

console.log('svg-path-properties export type:', typeof SvgPathProperties);
if (typeof SvgPathProperties !== 'function') {
  console.error('Could not resolve SvgPathProperties constructor. Got:', spp);
  process.exit(1);
}

const SVG_PATH = path.join(__dirname, '..', 'assets', 'tfl-map.svg');
const OUT_PATH = path.join(__dirname, '..', 'data', 'tube-schematic.json');

console.log('Reading:', SVG_PATH);
const svg = fs.readFileSync(SVG_PATH, 'utf8');
const $ = cheerio.load(svg, { xmlMode: true });

/* Map SVG path id -> internal line name.
   Multiple ids can map to the same line. */
const ID_TO_LINE = {
  'Bakerloo_line_route': 'bakerloo',
  'Central_line_route': 'central',
  'Circle_line_route': 'circle',
  'District_line_route': 'district',
  'District_Olympia_branch': 'district',
  'Hammersmith_and_City_line_route': 'hammersmith-city',
  'Jubilee_line_route': 'jubilee',
  'Metropolitan_line_route': 'metropolitan',
  'Northern_line_route': 'northern',
  'Piccadilly_line_route': 'piccadilly',
  'Victoria_line_route': 'victoria',
  'Waterloo_and_City_line_route': 'waterloo-city',
  'DLR_routes': 'dlr',
  'DLR_route_over': 'dlr',
  'Elizabeth_route_main': 'elizabeth',
  'Elizabeth_line_branch_east': 'elizabeth',
};

/* Sampling interval along each path, in SVG units.
   Smaller = smoother curve, more points.
   3 works well for a 2500-unit-wide map. */
const SAMPLE_STEP = 3;

const result = {}; // lineName -> [ [ [x,y], ... ], ... ]

function samplePath(d) {
  const props = new SvgPathProperties(d);
  const total = props.getTotalLength();
  if (!total || !isFinite(total)) return null;

  const points = [];
  for (let l = 0; l <= total; l += SAMPLE_STEP) {
    const { x, y } = props.getPointAtLength(l);
    points.push([
      Math.round(x * 100) / 100,
      Math.round(y * 100) / 100,
    ]);
  }

  // Ensure exact endpoint is included
  const end = props.getPointAtLength(total);
  points.push([
    Math.round(end.x * 100) / 100,
    Math.round(end.y * 100) / 100,
  ]);

  return points;
}

function pushPolyline(line, points) {
  if (!points || points.length < 2) return;
  if (!result[line]) result[line] = [];
  result[line].push(points);
}

$('path').each((_, el) => {
  const id = $(el).attr('id');
  if (!id) return;

  const line = ID_TO_LINE[id];
  if (!line) return;

  const d = $(el).attr('d');
  if (!d) {
    console.log(`  [warn] ${id}: no d attribute`);
    return;
  }

  let points;
  try {
    points = samplePath(d);
  } catch (e) {
    console.log(`  [error] ${id}: ${e.message}`);
    return;
  }

  if (!points) {
    console.log(`  [warn] ${id}: could not sample`);
    return;
  }

  console.log(`  ${id} → ${line}: ${points.length} sampled points`);
  pushPolyline(line, points);
});

console.log('\n=== Extracted lines ===');
const lineNames = Object.keys(result).sort();
for (const line of lineNames) {
  const polys = result[line];
  const pts = polys.reduce((s, p) => s + p.length, 0);
  console.log(
    `  ${line.padEnd(20)} ${String(polys.length).padStart(3)} polylines   ${String(pts).padStart(6)} points`
  );
}

const expected = new Set(Object.values(ID_TO_LINE));
const missing = [...expected].filter((l) => !result[l]);
if (missing.length) {
  console.log('\nMissing lines:', missing.join(', '));
} else {
  console.log('\nAll expected lines extracted.');
}

fs.writeFileSync(OUT_PATH, JSON.stringify(result, null, 2));
console.log(`\nWrote ${OUT_PATH}`);