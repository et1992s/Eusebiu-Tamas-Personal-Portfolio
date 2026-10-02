"""
Run once per dataset refresh. Trains CNN-LSTM, runs GA, dumps JSON
predictions under backend/app/services/trading/predictions/.

Not imported by the FastAPI app — run manually.
"""
import json
from pathlib import Path
import pandas as pd

from app.services.trading.ml.cnn_lstm_model import CNN_LSTM
from app.services.trading.ml.genetic_optimizer import GeneticAlgorithm

DATA = Path("data/algoseek_preprocessed.pkl")
OUT = Path("app/services/trading/predictions")
OUT.mkdir(parents=True, exist_ok=True)

def main():
    cnn = CNN_LSTM(DATA)
    df = cnn.load_data()

    for ticker in df.index.get_level_values('ticker').unique():
        try:
            y_pred, y_test, best_strategy = cnn.run_pipeline(stock_symbol=ticker)
        except Exception as exc:
            print(f"[SKIP] {ticker}: {exc}")
            continue

        payload = {
            "ticker": ticker,
            "y_pred": [float(v) for v in y_pred[:200].flatten()],
            "y_test": [float(v) for v in y_test[:200].flatten()],
            "best_strategy": {
                "buy": float(best_strategy[0]),
                "sell": float(best_strategy[1]),
                "stop_loss": float(best_strategy[2]),
                "take_profit": float(best_strategy[3]),
                "cnn_filters": int(best_strategy[6]),
                "lstm_units": int(best_strategy[7]),
                "learning_rate": float(best_strategy[13]),
                "batch_size": int(best_strategy[14]),
                "epochs": int(best_strategy[15]),
                "optimizer": str(best_strategy[16]),
            },
        }

        (OUT / f"{ticker}.json").write_text(json.dumps(payload))
        print(f"[OK] {ticker}")

if __name__ == "__main__":
    main()