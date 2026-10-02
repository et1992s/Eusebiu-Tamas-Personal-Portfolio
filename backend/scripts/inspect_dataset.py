import pickle
import numpy as np

DATA_PATH = "backend/data/algoseek_preprocessed.pkl"

with open(DATA_PATH, "rb") as f:
    d = pickle.load(f)

price_cols = ["first", "high", "low", "last"]

all_ohlc_missing = 0
partial_ohlc_missing = 0
ohlc_missing_zero_volume = 0
ohlc_missing_nonzero_volume = 0

valid_ohlc_zero_volume = 0
valid_ohlc_nonzero_volume = 0

missing_by_count = {
    1: 0,
    2: 0,
    3: 0,
    4: 0,
}

for ticker in d["tickers"]:
    df = d["data"][ticker]

    price_nan_count = df[price_cols].isna().sum(axis=1).to_numpy()
    volume = df["volume"].to_numpy(dtype=np.float64)

    for count in range(1, 5):
        missing_by_count[count] += int(
            (price_nan_count == count).sum()
        )

    missing_ohlc = price_nan_count > 0
    complete_ohlc = price_nan_count == 0

    all_ohlc_missing += int(
        (price_nan_count == 4).sum()
    )

    partial_ohlc_missing += int(
        ((price_nan_count >= 1) & (price_nan_count < 4)).sum()
    )

    ohlc_missing_zero_volume += int(
        (missing_ohlc & (volume == 0)).sum()
    )

    ohlc_missing_nonzero_volume += int(
        (missing_ohlc & (volume != 0)).sum()
    )

    valid_ohlc_zero_volume += int(
        (complete_ohlc & (volume == 0)).sum()
    )

    valid_ohlc_nonzero_volume += int(
        (complete_ohlc & (volume != 0)).sum()
    )


print("=== OHLC MISSINGNESS STRUCTURE ===")
print()

print("Rows with exactly 1 missing OHLC field:",
      missing_by_count[1])

print("Rows with exactly 2 missing OHLC fields:",
      missing_by_count[2])

print("Rows with exactly 3 missing OHLC fields:",
      missing_by_count[3])

print("Rows with all 4 OHLC fields missing:",
      missing_by_count[4])

print()
print("Total rows with any missing OHLC:",
      sum(missing_by_count.values()))

print()
print("=== VOLUME RELATIONSHIP ===")

print("Missing OHLC + zero volume:",
      ohlc_missing_zero_volume)

print("Missing OHLC + non-zero volume:",
      ohlc_missing_nonzero_volume)

print("Valid OHLC + zero volume:",
      valid_ohlc_zero_volume)

print("Valid OHLC + non-zero volume:",
      valid_ohlc_nonzero_volume)