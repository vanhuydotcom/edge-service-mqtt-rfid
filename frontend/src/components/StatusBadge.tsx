type BadgeVariant = 'success' | 'danger' | 'warning' | 'info' | 'neutral';
type BadgeSize = 'sm' | 'md';

interface StatusBadgeProps {
  variant: BadgeVariant;
  children: React.ReactNode;
  size?: BadgeSize;
  dot?: boolean;
}

const variantStyles: Record<BadgeVariant, string> = {
  success: 'bg-success-100 text-success-800',
  danger: 'bg-danger-100 text-danger-800',
  warning: 'bg-warning-100 text-warning-800',
  info: 'bg-circa-100 text-circa-800',
  neutral: 'bg-gray-100 text-gray-800',
};

const dotStyles: Record<BadgeVariant, string> = {
  success: 'bg-success-500',
  danger: 'bg-danger-500',
  warning: 'bg-warning-500',
  info: 'bg-circa-500',
  neutral: 'bg-gray-500',
};

const sizeStyles: Record<BadgeSize, string> = {
  sm: 'px-2 py-0.5 text-xs',
  md: 'px-2.5 py-1 text-sm',
};

export function StatusBadge({ variant, children, size = 'sm', dot = false }: StatusBadgeProps) {
  return (
    <span
      className={`
        inline-flex items-center font-medium rounded-full
        ${variantStyles[variant]}
        ${sizeStyles[size]}
      `}
    >
      {dot && (
        <span className={`w-1.5 h-1.5 rounded-full mr-1.5 ${dotStyles[variant]}`} />
      )}
      {children}
    </span>
  );
}

interface StatusIndicatorProps {
  status: boolean;
  size?: 'sm' | 'md' | 'lg';
}

const indicatorSizes = {
  sm: 'h-2 w-2',
  md: 'h-3 w-3',
  lg: 'h-4 w-4',
};

export function StatusIndicator({ status, size = 'md' }: StatusIndicatorProps) {
  return (
    <span
      className={`
        ${indicatorSizes[size]}
        rounded-full inline-block
        ${status ? 'bg-success-500' : 'bg-danger-500'}
      `}
    />
  );
}

