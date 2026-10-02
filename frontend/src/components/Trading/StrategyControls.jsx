import React from 'react';

const SLIDERS = [
  { key: 'buy_threshold',  label: 'Buy signal',  min: 0, max: 0.05, step: 0.001, pct: true },
  { key: 'sell_threshold', label: 'Sell signal', min: 0, max: 0.05, step: 0.001, pct: true },
  { key: 'stop_loss',      label: 'Stop loss',   min: 0, max: 0.10, step: 0.005, pct: true },
  { key: 'take_profit',    label: 'Take profit', min: 0, max: 0.10, step: 0.005, pct: true },
];

function StrategyControls({ params, onChange, disabled }) {
  return (
    <div className="strategy-controls">
      {SLIDERS.map((s) => (
        <label key={s.key} className="strategy-slider">
          <span className="strategy-slider-label">
            {s.label}
            <em>
              {s.pct
                ? `${(params[s.key] * 100).toFixed(2)}%`
                : params[s.key]}
            </em>
          </span>
          <input
            type="range"
            min={s.min}
            max={s.max}
            step={s.step}
            value={params[s.key]}
            disabled={disabled}
            onChange={(e) =>
              onChange(s.key, parseFloat(e.target.value))
            }
          />
        </label>
      ))}

      <label className="strategy-slider">
        <span className="strategy-slider-label">
          Position size
          <em>${params.position_size}</em>
        </span>
        <input
          type="range"
          min="100"
          max="10000"
          step="100"
          value={params.position_size}
          disabled={disabled}
          onChange={(e) =>
            onChange('position_size', parseInt(e.target.value, 10))
          }
        />
      </label>
    </div>
  );
}

export default StrategyControls;