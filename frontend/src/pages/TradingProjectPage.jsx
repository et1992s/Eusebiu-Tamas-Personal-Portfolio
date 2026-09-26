import React from 'react';
import { useTradingData, useTickers } from '../hooks/useTradingData';
import CandlestickChart from '../components/Chart/CandlestickChart';
import TickerSelector from '../components/Trading/TickerSelector';
import PricePanel from '../components/Trading/PricePanel';
import '../App.css';

function TradingProjectPage() {
  const [selectedTicker, setSelectedTicker] = React.useState('AAPL');
  const [barLimit, setBarLimit] = React.useState(100);

  const {
    tickers,
    loading: tickersLoading,
  } = useTickers();

  const {
    data,
    loading: dataLoading,
    error: tradingError,
  } = useTradingData(selectedTicker, barLimit);

  const barsLoaded =
    data?.bars ??
    data?.data?.length ??
    0;

  return (
    <section className="trading-page">

      <aside className="market-column">

        <div className="panel market-panel">

          <div className="panel-header">

            <div className="panel-title-group">

              <div className="section-icon market-icon">
                ⌁
              </div>

              <div>
                <h2>
                  Market Lab
                </h2>

                <p>
                  Trading data workspace
                </p>
              </div>

            </div>

            <span className="live-label">
              <span />
              DATA
            </span>

          </div>

          <div className="market-controls">

            <TickerSelector
              tickers={tickers}
              selectedTicker={selectedTicker}
              onSelect={setSelectedTicker}
              loading={tickersLoading}
            />

            <label className="bars-control">

              <span>
                Bars
              </span>

              <select
                value={barLimit}
                onChange={(event) =>
                  setBarLimit(
                    Number(event.target.value)
                  )
                }
              >
                <option value={50}>50</option>
                <option value={100}>100</option>
                <option value={200}>200</option>
                <option value={500}>500</option>
                <option value={1000}>1000</option>
              </select>

            </label>

          </div>

          <div className="market-stats">

            <div>
              <span>SYMBOL</span>
              <strong>{selectedTicker}</strong>
            </div>

            <div>
              <span>BARS</span>
              <strong>{barsLoaded || '—'}</strong>
            </div>

            <div>
              <span>STATUS</span>
              <strong
                className={
                  dataLoading
                    ? 'muted-value'
                    : ''
                }
              >
                {dataLoading
                  ? 'Loading'
                  : data
                    ? 'Ready'
                    : '—'}
              </strong>
            </div>

          </div>

          {tradingError && (
            <div className="market-error">

              <strong>
                Market data unavailable
              </strong>

              <span>
                {tradingError}
              </span>

            </div>
          )}

          {data &&
            data.data &&
            data.data.length > 0 && (
              <div className="price-panel-wrap">
                <PricePanel data={data} />
              </div>
            )}

          <div className="chart-wrap">

            {dataLoading ? (
              <div className="chart-placeholder">

                <div className="loader-ring" />

                <span>
                  Loading {selectedTicker} market data…
                </span>

              </div>
            ) : data?.data?.length ? (
              <CandlestickChart
                data={data.data}
                height={390}
              />
            ) : (
              <div className="chart-placeholder">

                <span>
                  No market data available
                </span>

              </div>
            )}

          </div>

          <div className="market-footer">

            <span>
              LOCAL DATA PIPELINE
            </span>

            <span className="pipeline-state">
              <i />
              CONNECTED
            </span>

          </div>

        </div>

      </aside>

    </section>
  );
}

export default TradingProjectPage;