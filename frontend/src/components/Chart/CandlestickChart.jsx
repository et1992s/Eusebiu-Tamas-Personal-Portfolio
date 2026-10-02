import { useEffect, useRef, useState } from 'react';
import * as LWC from 'lightweight-charts';

const {
  createChart,
  CandlestickSeries,
  LineSeries,
  AreaSeries,
  HistogramSeries,
  ColorType,
  PriceScaleMode,
  LineStyle,
  createSeriesMarkers, // <-- 1. Import the new function
} = LWC;

// ─────────────────────────────────────────────────────────────
// Formatters
// ─────────────────────────────────────────────────────────────

function toUnixTime(timestamp) {
  const ms = new Date(timestamp).getTime();
  if (!Number.isFinite(ms)) return null;
  return Math.floor(ms / 1000);
}

function formatLiveBars(data) {
  if (!Array.isArray(data)) return [];

  const bars = data
    .map((bar) => {
      const time = toUnixTime(bar?.timestamp);
      const open = Number(bar?.open);
      const high = Number(bar?.high);
      const low = Number(bar?.low);
      const close = Number(bar?.close);
      const volume = Number(bar?.volume);

      if (
        time === null ||
        !Number.isFinite(open) ||
        !Number.isFinite(high) ||
        !Number.isFinite(low) ||
        !Number.isFinite(close)
      ) {
        return null;
      }

      return {
        time,
        open,
        high,
        low,
        close,
        volume: Number.isFinite(volume) ? volume : 0,
      };
    })
    .filter(Boolean)
    .sort((a, b) => a.time - b.time);

  const unique = new Map();
  for (const bar of bars) unique.set(bar.time, bar);
  return Array.from(unique.values()).sort((a, b) => a.time - b.time);
}

function formatVolumeData(liveBars) {
  return liveBars.map((bar) => ({
    time: bar.time,
    value: bar.volume,
    color:
      bar.close >= bar.open
        ? 'rgba(34, 197, 94, 0.55)'
        : 'rgba(239, 68, 68, 0.55)',
  }));
}

// ─────────────────────────────────────────────────────────────
// Badge
// ─────────────────────────────────────────────────────────────

function LiveBadge({ timestamp }) {
  const formatted = timestamp
    ? new Date(timestamp).toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      })
    : null;

  return (
    <div
      style={{
        position: 'absolute',
        top: 10,
        left: 12,
        zIndex: 5,
        display: 'flex',
        alignItems: 'center',
        gap: 7,
        padding: '5px 8px',
        borderRadius: 4,
        background: 'rgba(8, 12, 18, 0.88)',
        border: '1px solid rgba(57, 255, 20, 0.25)',
        color: '#9cff57',
        fontSize: 9,
        fontWeight: 700,
        letterSpacing: '0.08em',
        textTransform: 'uppercase',
        pointerEvents: 'none',
      }}
    >
      <span
        style={{
          width: 6,
          height: 6,
          borderRadius: '50%',
          background: '#39ff14',
          boxShadow: '0 0 7px rgba(57, 255, 20, 0.65)',
        }}
      />
      LIVE ALPACA
      {formatted && (
        <span
          style={{
            color: '#94a3b8',
            fontWeight: 500,
            letterSpacing: '0.04em',
          }}
        >
          {formatted}
        </span>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Chart
// ─────────────────────────────────────────────────────────────

const CandlestickChart = ({
  data = [],
  height = 390,
  chartType = 'candlestick',
  indicators = [],
  markers = [],
  showVolume = true,
  logScale = false,
  strategyLines = null,
}) => {
  const containerRef = useRef(null);
  const chartRef = useRef(null);
  const seriesRef = useRef(null);
  const volumeSeriesRef = useRef(null);
  const indicatorSeriesRef = useRef([]);
  const priceLinesRef = useRef([]);
  const seriesMarkersRef = useRef(null); // <-- 2. Add a ref for the markers primitive

  const [chartVersion, setChartVersion] = useState(0);

  const latestTimestamp =
    Array.isArray(data) && data.length > 0
      ? data[data.length - 1]?.timestamp
      : null;

  // ── Effect 1: chart lifecycle ─────────────────────────────
  useEffect(() => {
    if (!containerRef.current) return undefined;

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth || 600,
      height,
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#94a3b8',
        panes: {
          separatorColor: 'rgba(148, 163, 184, 0.15)',
          separatorHoverColor: 'rgba(148, 163, 184, 0.30)',
          enableResize: true,
        },
      },
      grid: {
        vertLines: { color: 'rgba(148, 163, 184, 0.07)' },
        horzLines: { color: 'rgba(148, 163, 184, 0.07)' },
      },
      crosshair: { mode: 1 },
      rightPriceScale: {
        borderColor: 'rgba(148, 163, 184, 0.15)',
        mode: logScale ? PriceScaleMode.Logarithmic : PriceScaleMode.Normal,
      },
      timeScale: {
        borderColor: 'rgba(148, 163, 184, 0.15)',
        timeVisible: true,
        secondsVisible: false,
        rightOffset: 5,
        barSpacing: 7,
      },
      handleScroll: {
        mouseWheel: true,
        pressedMouseMove: true,
        horzTouchDrag: true,
        vertTouchDrag: true,
      },
      handleScale: {
        mouseWheel: true,
        pinch: true,
        axisPressedMouseMove: true,
      },
    });

    chartRef.current = chart;
    setChartVersion((v) => v + 1);

    const resizeObserver = new ResizeObserver(() => {
      if (!containerRef.current) return;
      chart.applyOptions({ width: containerRef.current.clientWidth || 600 });
    });
    resizeObserver.observe(containerRef.current);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
      volumeSeriesRef.current = null;
      indicatorSeriesRef.current = [];
      priceLinesRef.current = [];
      seriesMarkersRef.current = null; // <-- 3. Clean up the markers ref
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [height]);

  // ── Effect 1b: log-scale toggle ───────────────────────────
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;

    chart.applyOptions({
      rightPriceScale: {
        mode: logScale ? PriceScaleMode.Logarithmic : PriceScaleMode.Normal,
      },
    });
  }, [logScale, chartVersion]);

  // ── Effect 2: main price series ───────────────────────────
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;

    if (seriesRef.current) {
      chart.removeSeries(seriesRef.current);
      seriesRef.current = null;
    }

    let mainSeries;
    if (chartType === 'line') {
      mainSeries = chart.addSeries(LineSeries, {
        color: '#3b82f6',
        lineWidth: 2,
      });
    } else if (chartType === 'area') {
      mainSeries = chart.addSeries(AreaSeries, {
        topColor: 'rgba(59, 130, 246, 0.5)',
        bottomColor: 'rgba(59, 130, 246, 0.0)',
        lineColor: '#3b82f6',
      });
    } else {
      mainSeries = chart.addSeries(CandlestickSeries, {
        upColor: '#22c55e',
        downColor: '#ef4444',
        borderUpColor: '#22c55e',
        borderDownColor: '#ef4444',
        wickUpColor: '#22c55e',
        wickDownColor: '#ef4444',
      });
    }

    seriesRef.current = mainSeries;

    const liveBars = formatLiveBars(data);

    if (chartType === 'line' || chartType === 'area') {
      mainSeries.setData(liveBars.map((b) => ({ time: b.time, value: b.close })));
    } else {
      mainSeries.setData(liveBars);
    }

    // 4. Removed the setMarkers call from here. It's now handled in its own effect.
    
    if (liveBars.length > 0) chart.timeScale().fitContent();
  }, [data, chartType, chartVersion]); // <-- Removed markers from dependencies here

  // ── Effect 2b: markers (v5 API) ───────────────────────────
  useEffect(() => {
    const series = seriesRef.current;
    if (!series) return;

    // 5. Create the markers primitive if it doesn't exist
    if (!seriesMarkersRef.current) {
      seriesMarkersRef.current = createSeriesMarkers(series, markers);
    } else {
      // 6. Otherwise, just update the existing primitive
      seriesMarkersRef.current.setMarkers(markers);
    }
  }, [markers, chartVersion]); // <-- This effect depends on markers and the chart version

  // ── Effect 3: volume histogram (pane 1) ───────────────────
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;

    const liveBars = formatLiveBars(data);
    const hasVolume = showVolume && liveBars.some((b) => b.volume > 0);

    if (!hasVolume) {
      if (volumeSeriesRef.current) {
        try {
          chart.removeSeries(volumeSeriesRef.current);
        } catch {
          /* already gone */
        }
        volumeSeriesRef.current = null;
      }
      return;
    }

    if (!volumeSeriesRef.current) {
      volumeSeriesRef.current = chart.addSeries(
        HistogramSeries,
        {
          priceFormat: { type: 'volume' },
          priceLineVisible: false,
          lastValueVisible: false,
        },
        1,
      );

      const panes = chart.panes();
      if (panes.length >= 2) {
        panes[0].setStretchFactor(3);
        panes[1].setStretchFactor(1);
      }
    }

    volumeSeriesRef.current.setData(formatVolumeData(liveBars));
  }, [data, showVolume, chartVersion]);

  // ── Effect 4: indicator overlays ──────────────────────────
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;

    indicatorSeriesRef.current.forEach((s) => {
      try {
        chart.removeSeries(s);
      } catch {
        /* already removed */
      }
    });
    indicatorSeriesRef.current = [];

    indicators.forEach((indicator) => {
      const s = chart.addSeries(LineSeries, {
        color: indicator.color || '#f59e0b',
        lineWidth: 2,
        title: indicator.name,
      });
      s.setData(indicator.data);
      indicatorSeriesRef.current.push(s);
    });
  }, [indicators, chartVersion]);

  // ── Effect 5: strategy price lines (entry / SL / TP×2) ────
  useEffect(() => {
    const chart = chartRef.current;
    const series = seriesRef.current;
    if (!series || !chart) return;

    priceLinesRef.current.forEach((line) => {
      try {
        series.removePriceLine(line);
      } catch {
        /* already detached */
      }
    });
    priceLinesRef.current = [];

    if (!strategyLines) return;

    // Only draw the envelope when there's an active signal
    if (strategyLines.signal === 'NONE') return;

    // Backward-compat: fall back to a single takeProfit if the caller
    // hasn't yet been updated to pass takeProfitModel / takeProfitUser.
    const tpModel =
      strategyLines.takeProfitModel ?? strategyLines.takeProfit;
    const tpUser =
      strategyLines.takeProfitUser ?? strategyLines.takeProfit;

    const defs = [
      strategyLines.entry != null &&
        Number.isFinite(strategyLines.entry) && {
          price: strategyLines.entry,
          color: '#fbbf24',           // amber — reference line
          lineStyle: LineStyle.Solid,
          title: 'ENTRY',
        },
      tpModel != null &&
        Number.isFinite(tpModel) && {
          price: tpModel,
          color: '#22c55e',           // bright green — ML target
          lineStyle: LineStyle.Solid,
          title: 'TP (ML)',
        },
      tpUser != null &&
        Number.isFinite(tpUser) &&
        Math.abs(tpUser - tpModel) > 0.01 && {
          price: tpUser,
          color: '#16a34a',           // muted green — user's slider
          lineStyle: LineStyle.Dashed,
          title: 'TP',
        },
      strategyLines.stopLoss != null &&
        Number.isFinite(strategyLines.stopLoss) && {
          price: strategyLines.stopLoss,
          color: '#ef4444',
          lineStyle: LineStyle.Dashed,
          title: 'SL',
        },
    ].filter(Boolean);

    defs.forEach((def) => {
      const line = series.createPriceLine({
        price: def.price,
        color: def.color,
        lineWidth: 2,
        lineStyle: def.lineStyle,
        axisLabelVisible: true,
        title: def.title,
      });
      priceLinesRef.current.push(line);
    });

    try {
      series.priceScale().applyOptions({ autoScale: true });
    } catch {
      /* handled internally by the library in some versions */
    }
  }, [strategyLines, chartType, chartVersion]);

  return (
    <div
      style={{
        position: 'relative',
        width: '100%',
        height: `${height}px`,
      }}
    >
      <LiveBadge timestamp={latestTimestamp} />
      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
    </div>
  );
};

export default CandlestickChart;