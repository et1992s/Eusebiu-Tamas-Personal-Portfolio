const fs = require('fs');
const path = require('path');
const cheerio = require('cheerio');

const SVG_PATH = path.join(__dirname, '..', 'assets', 'tfl-map.svg');
console.log('Looking for SVG at:', SVG_PATH);
console.log('Exists?', fs.existsSync(SVG_PATH));

if (!fs.existsSync(SVG_PATH)) {
  console.error('\nFile not found. Check the path.');
  process.exit(1);
}

const svg = fs.readFileSync(SVG_PATH, 'utf8');
const $ = cheerio.load(svg, { xmlMode: true });

const classes = new Set();
const ids = new Set();
const tagCounts = {};

$('*').each((_, el) => {
  const tag = el.tagName;
  tagCounts[tag] = (tagCounts[tag] || 0) + 1;
  if (tag === 'path' || tag === 'polyline' || tag === 'line') {
    const cls = $(el).attr('class');
    const id = $(el).attr('id');
    if (cls) cls.split(/\s+/).forEach((c) => c && classes.add(c));
    if (id) ids.add(id);
  }
});

console.log('\n=== SVG tag counts ===');
console.log(tagCounts);

console.log('\n=== Unique class names on path/polyline (first 80) ===');
console.log([...classes].sort().slice(0, 80));

console.log('\n=== Unique ids on path/polyline (first 80) ===');
console.log([...ids].sort().slice(0, 80));

console.log('\n=== Sample of first 3 <path> elements ===');
$('path').slice(0, 3).each((i, el) => {
  console.log(`\n--- path #${i} ---`);
  console.log('id:', $(el).attr('id'));
  console.log('class:', $(el).attr('class'));
  console.log('style:', $(el).attr('style'));
  console.log('d (first 120 chars):', ($(el).attr('d') || '').slice(0, 120));
});

console.log('\n=== Sample of first 3 <polyline> elements ===');
$('polyline').slice(0, 3).each((i, el) => {
  console.log(`\n--- polyline #${i} ---`);
  console.log('id:', $(el).attr('id'));
  console.log('class:', $(el).attr('class'));
  console.log('style:', $(el).attr('style'));
  console.log('points (first 120 chars):', ($(el).attr('points') || '').slice(0, 120));
});

console.log('\n=== SVG root ===');
const svgRoot = $('svg').first();
console.log('viewBox:', svgRoot.attr('viewBox'));
console.log('width:', svgRoot.attr('width'));
console.log('height:', svgRoot.attr('height'));