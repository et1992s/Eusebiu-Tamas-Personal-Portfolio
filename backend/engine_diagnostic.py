"""
test_bars.py - Test get_bars method
"""

from app.services.trading.simulation.engine import TradingEngine
import time

print("=" * 60)
print("TESTING GET_BARS")
print("=" * 60)

print("\n[1] Loading engine...")
engine = TradingEngine()
engine.load_data()
print(f"    Loaded {len(engine.tickers)} tickers")

print("\n[2] Checking AAPL data...")
if 'AAPL' in engine.ticker_data:
    aapl_df = engine.ticker_data['AAPL']
    print(f"    AAPL data shape: {aapl_df.shape}")
    print(f"    AAPL columns: {aapl_df.columns.tolist()}")
    print(f"    AAPL index type: {type(aapl_df.index)}")
    print(f"    First 3 rows:\n{aapl_df.head(3)}")
else:
    print("    ❌ AAPL not found!")
    exit()

print("\n[3] Getting bars (limit 5)...")
start = time.time()
bars = engine.get_bars('AAPL', 5)
elapsed = time.time() - start
print(f"    Time: {elapsed:.3f}s")

if bars:
    print(f"    ✅ Found {len(bars)} bars")
    for b in bars:
        print(f"      {b['timestamp']} -> Close: ${b['close']:.2f} | Vol: {b['volume']}")
else:
    print("    ❌ No bars returned")

print("\n[4] Getting 2015 bars (limit 5)...")
start = time.time()
bars_2015 = engine.get_bars_2015('AAPL', 5)
elapsed = time.time() - start
print(f"    Time: {elapsed:.3f}s")

if bars_2015:
    print(f"    ✅ Found {len(bars_2015)} bars")
    for b in bars_2015:
        print(f"      {b['timestamp']} -> Close: ${b['close']:.2f} | Vol: {b['volume']}")
else:
    print("    ❌ No bars returned")

print("\n" + "=" * 60)
print("✅ TEST COMPLETE")
print("=" * 60)