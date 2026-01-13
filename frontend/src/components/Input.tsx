import { InputHTMLAttributes, forwardRef } from 'react';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  hint?: string;
  error?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, hint, error, className = '', id, ...props }, ref) => {
    const inputId = id || label?.toLowerCase().replace(/\s+/g, '-');

    return (
      <div className="space-y-1">
        {label && (
          <label htmlFor={inputId} className="block text-sm font-medium text-gray-700">
            {label}
          </label>
        )}
        <input
          ref={ref}
          id={inputId}
          className={`
            mt-1 block w-full rounded-md shadow-sm
            border px-3 py-2 text-sm
            ${error
              ? 'border-danger-300 focus:border-danger-500 focus:ring-danger-500'
              : 'border-gray-300 focus:border-circa-500 focus:ring-circa-500'
            }
            ${className}
          `}
          {...props}
        />
        {hint && !error && (
          <p className="text-xs text-gray-500">{hint}</p>
        )}
        {error && (
          <p className="text-xs text-danger-600">{error}</p>
        )}
      </div>
    );
  }
);

Input.displayName = 'Input';

interface CheckboxProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label: string;
  description?: string;
}

export function Checkbox({ label, description, className = '', ...props }: CheckboxProps) {
  return (
    <div className="flex items-start">
      <input
        type="checkbox"
        className={`
          h-4 w-4 rounded border-gray-300
          text-circa-600 focus:ring-circa-500
          ${className}
        `}
        {...props}
      />
      <div className="ml-2">
        <label className="block text-sm text-gray-700">{label}</label>
        {description && (
          <p className="text-xs text-gray-500">{description}</p>
        )}
      </div>
    </div>
  );
}

