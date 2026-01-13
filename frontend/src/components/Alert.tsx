import { ReactNode } from 'react';

type AlertVariant = 'success' | 'error' | 'warning' | 'info';

interface AlertProps {
  variant: AlertVariant;
  children: ReactNode;
  loading?: boolean;
  onDismiss?: () => void;
}

const variantStyles: Record<AlertVariant, { bg: string; text: string; icon: string }> = {
  success: {
    bg: 'bg-success-50 border-success-200',
    text: 'text-success-700',
    icon: '✓',
  },
  error: {
    bg: 'bg-danger-50 border-danger-200',
    text: 'text-danger-700',
    icon: '✕',
  },
  warning: {
    bg: 'bg-warning-50 border-warning-200',
    text: 'text-warning-700',
    icon: '⚠',
  },
  info: {
    bg: 'bg-circa-50 border-circa-200',
    text: 'text-circa-700',
    icon: 'ℹ',
  },
};

export function Alert({ variant, children, loading = false, onDismiss }: AlertProps) {
  const styles = variantStyles[variant];

  return (
    <div
      className={`px-4 py-3 rounded-md border flex items-center justify-between ${styles.bg} ${styles.text}`}
    >
      <div className="flex items-center">
        {loading ? (
          <svg
            className="animate-spin mr-3 h-5 w-5"
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
        ) : (
          <span className="mr-3 font-bold">{styles.icon}</span>
        )}
        {children}
      </div>
      {onDismiss && (
        <button
          onClick={onDismiss}
          className="ml-4 text-current opacity-60 hover:opacity-100 transition-opacity"
        >
          ✕
        </button>
      )}
    </div>
  );
}

