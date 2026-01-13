type SpinnerSize = 'sm' | 'md' | 'lg' | 'xl';
type SpinnerVariant = 'primary' | 'white' | 'gray';

interface SpinnerProps {
  size?: SpinnerSize;
  variant?: SpinnerVariant;
  className?: string;
}

const sizeStyles: Record<SpinnerSize, string> = {
  sm: 'h-4 w-4',
  md: 'h-6 w-6',
  lg: 'h-8 w-8',
  xl: 'h-10 w-10',
};

const variantStyles: Record<SpinnerVariant, string> = {
  primary: 'text-circa-600',
  white: 'text-white',
  gray: 'text-gray-400',
};

export function Spinner({ size = 'md', variant = 'primary', className = '' }: SpinnerProps) {
  return (
    <svg
      className={`animate-spin ${sizeStyles[size]} ${variantStyles[variant]} ${className}`}
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      />
    </svg>
  );
}

interface LoadingStateProps {
  message?: string;
  size?: SpinnerSize;
}

export function LoadingState({ message = 'Loading...', size = 'lg' }: LoadingStateProps) {
  return (
    <div className="text-center py-12 bg-circa-50 rounded-lg border border-circa-200">
      <Spinner size={size} className="mx-auto mb-3" />
      <p className="text-circa-600">{message}</p>
    </div>
  );
}

export function LoadingOverlay() {
  return (
    <div className="absolute inset-0 bg-white/75 flex items-center justify-center rounded-lg">
      <Spinner size="lg" />
    </div>
  );
}

