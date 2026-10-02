/**
 * Alpaca crypto symbols contain a slash ("BTC/USD"), which breaks URLs.
 * Normalizes to a dash for transport and denormalize on the backend.
 */
export function encodeTicker(ticker) {
  if (!ticker) return '';
  return ticker.replace('/', '-').toUpperCase().trim();
}

export function decodeTicker(ticker) {
  if (!ticker) return '';
  return ticker.replace('-', '/').toUpperCase().trim();
}

export function isCryptoTicker(ticker) {
  return typeof ticker === 'string' && ticker.includes('/');
}