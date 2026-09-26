"""
test_simple_load.py - Simple test to see what's happening
"""

import pandas as pd
import time
import sys

print("Starting load...")
sys.stdout.flush()

start = time.time()

try:
    # Try loading just the first 1000 rows
    df = pd.read_csv('data/algoseek.csv', nrows=10000000)
    print(f"✅ Loaded 1000 rows in {time.time()-start:.2f}s")
    print(f"Shape: {df.shape}")
except Exception as e:
    print(f"❌ Error: {e}")

sys.stdout.flush()