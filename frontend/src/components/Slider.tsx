import { InputHTMLAttributes } from 'react';

interface SliderProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label?: string;
  value: number;
  min?: number;
  max?: number;
  unit?: string;
  showValue?: boolean;
  changed?: boolean;
  originalValue?: number;
  diff?: number | null;
}

export function Slider({
  label,
  value,
  min = 0,
  max = 100,
  unit = '',
  showValue = true,
  changed = false,
  originalValue,
  diff,
  className = '',
  ...props
}: SliderProps) {
  return (
    <div className={`p-4 rounded-lg border-2 transition-colors ${
      changed ? 'border-warning-300 bg-warning-50' : 'border-gray-200 bg-gray-50'
    } ${className}`}>
      {/* Header */}
      {label && (
        <div className="flex justify-between items-center mb-3">
          <span className="text-sm font-semibold text-gray-700">{label}</span>
          {changed && diff !== null && diff !== undefined && (
            <span className={`text-xs px-2 py-0.5 rounded font-medium ${
              diff > 0 ? 'bg-success-100 text-success-700' : 'bg-danger-100 text-danger-700'
            }`}>
              {diff > 0 ? '+' : ''}{diff}
            </span>
          )}
        </div>
      )}

      {/* Value Display */}
      {showValue && (
        <div className="text-center mb-3">
          <div className="text-3xl font-bold text-circa-600">{value}</div>
          {unit && <div className="text-xs text-gray-400">{unit}</div>}
        </div>
      )}

      {/* Range Input */}
      <input
        type="range"
        min={min}
        max={max}
        value={value}
        className="w-full"
        {...props}
      />

      {/* Min/Max Labels */}
      <div className="flex justify-between text-xs text-gray-400 mt-1">
        <span>{min}</span>
        <span>{max} {unit}</span>
      </div>

      {/* Original Value Indicator */}
      {changed && originalValue !== undefined && (
        <div className="mt-2 text-center">
          <span className="text-xs text-gray-400">
            Original: {originalValue} {unit}
          </span>
        </div>
      )}
    </div>
  );
}

