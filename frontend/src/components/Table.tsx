import { ReactNode } from 'react';

interface TableProps {
  children: ReactNode;
  className?: string;
}

interface TableHeaderProps {
  columns: string[];
}

interface TableRowProps {
  children: ReactNode;
  highlight?: 'danger' | 'warning' | 'success' | 'none';
  className?: string;
}

interface TableCellProps {
  children: ReactNode;
  className?: string;
  mono?: boolean;
}

export function Table({ children, className = '' }: TableProps) {
  return (
    <div className={`overflow-x-auto ${className}`}>
      <table className="min-w-full divide-y divide-gray-200">
        {children}
      </table>
    </div>
  );
}

export function TableHeader({ columns }: TableHeaderProps) {
  return (
    <thead className="bg-gray-50">
      <tr>
        {columns.map((col, idx) => (
          <th
            key={idx}
            className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase"
          >
            {col}
          </th>
        ))}
      </tr>
    </thead>
  );
}

export function TableBody({ children }: { children: ReactNode }) {
  return (
    <tbody className="bg-white divide-y divide-gray-200">
      {children}
    </tbody>
  );
}

const highlightStyles = {
  danger: 'bg-danger-50',
  warning: 'bg-warning-50',
  success: 'bg-success-50',
  none: '',
};

export function TableRow({ children, highlight = 'none', className = '' }: TableRowProps) {
  return (
    <tr className={`hover:bg-gray-50 ${highlightStyles[highlight]} ${className}`}>
      {children}
    </tr>
  );
}

export function TableCell({ children, className = '', mono = false }: TableCellProps) {
  return (
    <td className={`px-6 py-4 whitespace-nowrap text-sm ${mono ? 'font-mono' : ''} ${className}`}>
      {children}
    </td>
  );
}

interface EmptyRowProps {
  colSpan: number;
  message?: string;
}

export function EmptyRow({ colSpan, message = 'No data found' }: EmptyRowProps) {
  return (
    <tr>
      <td colSpan={colSpan} className="px-6 py-8 text-center text-gray-500">
        {message}
      </td>
    </tr>
  );
}

