const fs = require('fs');
const path = require('path');
const cheerio = require('cheerio');

const SVG_PATH = path.join(__dirname, '..', 'assets', 'tfl-map.svg');

const svg = fs.readFileSync(SVG_PATH, 'utf8');
const $ = cheerio.load(svg, { xmlMode: true });

const LINE_GROUPS = {
  Bakerloo_line_stations: 'bakerloo',
  Central_line_stations: 'central',
  Circle_line_stations: 'circle',
  District_line_stations: 'district',
  Hammersmith_And_City_line_stations: 'hammersmith-city',
  Jubilee_line_stations: 'jubilee',
  Metropolitan_line_stations: 'metropolitan',
  Northern_line_stations: 'northern',
  Piccadilly_line_stations: 'piccadilly',
  Victoria_line_stations: 'victoria',
  Docklands_Light_Railway_stations: 'dlr',
  Lioness_line_stations: 'lioness',
  Mildmay_line_stations: 'mildmay',
  Suffragette_line_stations: 'suffragette',
  Windrush_line_stations: 'windrush',
  Weaver_line_stations: 'weaver',
  Liberty_line_station: 'liberty',
  Elizabeth_Line_stations: 'elizabeth',
  Tramlink_stations: 'tramlink',
};

const SHARED_GROUPS = {
  Metropolitan_Piccadilly_stations_shared: 'shared',
  Bakerloo_Lioness_shared_stations: 'shared',
  Multiple_interchanges_group: 'interchange',
};

function parseNumbers(value) {
  return value
    .trim()
    .split(/[\s,]+/)
    .filter(Boolean)
    .map(Number);
}

function multiplyMatrices(a, b) {
  return [
    [
      a[0][0] * b[0][0] + a[0][1] * b[1][0],
      a[0][0] * b[0][1] + a[0][1] * b[1][1],
      a[0][0] * b[0][2] + a[0][1] * b[1][2] + a[0][2],
    ],
    [
      a[1][0] * b[0][0] + a[1][1] * b[1][0],
      a[1][0] * b[0][1] + a[1][1] * b[1][1],
      a[1][0] * b[0][2] + a[1][1] * b[1][2] + a[1][2],
    ],
    [0, 0, 1],
  ];
}

function identityMatrix() {
  return [
    [1, 0, 0],
    [0, 1, 0],
    [0, 0, 1],
  ];
}

function transformMatrix(transform) {
  let result = identityMatrix();

  if (!transform) {
    return result;
  }

  const regex = /([a-zA-Z]+)\s*\(([^)]*)\)/g;
  let match;

  while ((match = regex.exec(transform)) !== null) {
    const type = match[1];
    const values = parseNumbers(match[2]);

    let matrix = identityMatrix();

    if (type === 'translate') {
      const tx = values[0] || 0;
      const ty = values.length > 1 ? values[1] : 0;

      matrix = [
        [1, 0, tx],
        [0, 1, ty],
        [0, 0, 1],
      ];
    }

    else if (type === 'rotate') {
      const angle = (values[0] || 0) * Math.PI / 180;
      const cos = Math.cos(angle);
      const sin = Math.sin(angle);

      const rotation = [
        [cos, -sin, 0],
        [sin, cos, 0],
        [0, 0, 1],
      ];

      if (values.length >= 3) {
        const cx = values[1];
        const cy = values[2];

        const toOrigin = [
          [1, 0, -cx],
          [0, 1, -cy],
          [0, 0, 1],
        ];

        const back = [
          [1, 0, cx],
          [0, 1, cy],
          [0, 0, 1],
        ];

        matrix = multiplyMatrices(
          back,
          multiplyMatrices(rotation, toOrigin)
        );
      } else {
        matrix = rotation;
      }
    }

    else if (type === 'scale') {
      const sx = values[0] ?? 1;
      const sy = values.length > 1 ? values[1] : sx;

      matrix = [
        [sx, 0, 0],
        [0, sy, 0],
        [0, 0, 1],
      ];
    }

    else if (type === 'matrix' && values.length === 6) {
      const [a, b, c, d, e, f] = values;

      matrix = [
        [a, c, e],
        [b, d, f],
        [0, 0, 1],
      ];
    }

    result = multiplyMatrices(result, matrix);
  }

  return result;
}

function applyMatrix(matrix, x, y) {
  return {
    x: matrix[0][0] * x +
       matrix[0][1] * y +
       matrix[0][2],

    y: matrix[1][0] * x +
       matrix[1][1] * y +
       matrix[1][2],
  };
}

function extractStationPosition(element) {
  let x = Number(element.attr('x'));
  let y = Number(element.attr('y'));

  if (!Number.isFinite(x)) x = 0;
  if (!Number.isFinite(y)) y = 0;

  let matrix = identityMatrix();

  const ancestors = element.parents().get().reverse();

  for (const ancestor of ancestors) {
    const transform = $(ancestor).attr('transform');

    if (transform) {
      matrix = multiplyMatrices(
        matrix,
        transformMatrix(transform)
      );
    }
  }

  const ownTransform = element.attr('transform');

  if (ownTransform) {
    matrix = multiplyMatrices(
      matrix,
      transformMatrix(ownTransform)
    );
  }

  return applyMatrix(matrix, x, y);
}

const stations = new Map();

function getStationIdFromText(text) {
  return text
    .replace(/\s+/g, ' ')
    .replace(/[.'’]/g, '')
    .replace(/&/g, 'And')
    .replace(/[^A-Za-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '');
}

function collectNativeStationNodes(groupId, groupType) {
  const group = $(`#${groupId}`);

  if (!group.length) {
    return;
  }

  group.find('use[id]').each((_, el) => {
    const node = $(el);
    const id = node.attr('id');

    if (!id || id.endsWith('_acc')) {
      return;
    }

    const coordinate = extractStationPosition(node);

    if (!Number.isFinite(coordinate.x) || !Number.isFinite(coordinate.y)) {
      return;
    }

    if (!stations.has(id)) {
      stations.set(id, {
        id,
        coordinate: [
          Number(coordinate.x.toFixed(3)),
          Number(coordinate.y.toFixed(3)),
        ],
        lines: [],
        sources: [],
      });
    }

    stations.get(id).sources.push({
      group: groupId,
      type: groupType,
      href: node.attr('xlink:href') || node.attr('href') || null,
    });
  });
}

function collectLineMembership(groupId, line) {
  const group = $(`#${groupId}`);

  if (!group.length) {
    return;
  }

  group.find('text').each((_, el) => {
    const node = $(el);

    const text = node
      .clone()
      .children()
      .remove()
      .end()
      .text()
      .trim();

    const fullText = node.text().replace(/\s+/g, ' ').trim();

    const stationName = fullText || text;

    if (!stationName) {
      return;
    }

    const normalizedId = getStationIdFromText(stationName);

    const candidates = [
      normalizedId,
      normalizedId.replace(/^St_/, 'St_'),
    ];

    for (const candidate of candidates) {
      if (stations.has(candidate)) {
        const station = stations.get(candidate);

        if (!station.lines.includes(line)) {
          station.lines.push(line);
        }

        return;
      }
    }
  });
}

for (const [groupId, type] of Object.entries(SHARED_GROUPS)) {
  collectNativeStationNodes(groupId, type);
}

for (const [groupId] of Object.entries(LINE_GROUPS)) {
  collectNativeStationNodes(groupId, 'line');
}

for (const [groupId, line] of Object.entries(LINE_GROUPS)) {
  collectLineMembership(
    groupId.replace('_stations', '').replace('_station', ''),
    line
  );
}

const NAME_GROUPS = {
  stname_Bakerloo_line: 'bakerloo',
  stname_Central_line: 'central',
  stname_Circle_line: 'circle',
  stname_District_line_and_Hammersmith_And_City_line: [
    'district',
    'hammersmith-city',
  ],
  stname_Jubilee_line: 'jubilee',
  stname_Metropolitan_line: 'metropolitan',
  stname_Northern_line: 'northern',
  stname_Piccadilly_line: 'piccadilly',
  stname_Victoria_line: 'victoria',
  stname_Docklands_Light_Railway: 'dlr',
  stname_Watford_DC_Line: 'watford-dc',
  stname_West_London_Line: 'west-london',
  stname_North_London_Line: 'north-london',
  stname_Gospel_Oak_to_Barking_Line: 'gospel-oak-barking',
  stname_East_London_Line: 'east-london',
  stname_Seven_Sisters_Line: 'seven-sisters',
  stname_Chingford_Line: 'chingford',
  stname_Romford_to_Upminster_Line: 'romford-upminster',
  stname_elizabeth: 'elizabeth',
  stname_Tramlink: 'tramlink',
};

function findStationByName(name) {
  const normalized = getStationIdFromText(name);

  if (stations.has(normalized)) {
    return stations.get(normalized);
  }

  const aliases = {
    Regents_Park: 'Regents_Park',
    St_Pauls: 'St_Pauls',
    Kings_Cross_St_Pancras: 'Kings_Cross_St_Pancras',
    Queens_Park: 'Queens_Park',
    Euston_Square: 'Euston_Square',
  };

  const alias = aliases[normalized];

  if (alias && stations.has(alias)) {
    return stations.get(alias);
  }

  return null;
}

for (const [groupId, lines] of Object.entries(NAME_GROUPS)) {
  const group = $(`#${groupId}`);

  if (!group.length) {
    continue;
  }

  const lineList = Array.isArray(lines) ? lines : [lines];

  group.find('text').each((_, el) => {
    const name = $(el).text().replace(/\s+/g, ' ').trim();

    if (!name) {
      return;
    }

    const station = findStationByName(name);

    if (!station) {
      return;
    }

    for (const line of lineList) {
      if (!station.lines.includes(line)) {
        station.lines.push(line);
      }
    }
  });
}

const output = Object.fromEntries(
  [...stations.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
);

console.log(`Extracted ${Object.keys(output).length} unique station IDs`);

console.log('\n=== SAMPLE STATIONS ===');

for (const id of [
  'Baker_Street',
  'Archway',
  'Tower_Gateway',
  'Tower_Hill',
  'Canada_Water',
  'Green_Park',
  'Victoria',
  'Waterloo',
]) {
  console.log(`\n${id}:`);

  if (!output[id]) {
    console.log('  NOT FOUND');
    continue;
  }

  console.log(JSON.stringify(output[id], null, 2));
}

const OUTPUT_PATH = path.join(
  __dirname,
  '..',
  'data',
  'svg-stations-extracted.json'
);

fs.mkdirSync(path.dirname(OUTPUT_PATH), { recursive: true });

fs.writeFileSync(
  OUTPUT_PATH,
  JSON.stringify(output, null, 2),
  'utf8'
);

console.log(`\nWritten to: ${OUTPUT_PATH}`);