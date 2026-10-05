import React from 'react';
import { cn } from '@/lib/utils';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'default' | 'outline' | 'ghost' | 'destructive' | 'secondary';
  size?: 'default' | 'sm' | 'lg' | 'icon';
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'default', size = 'default', ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(
          "inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-slate-400 disabled:pointer-events-none disabled:opacity-50",
          {
            "bg-teal-600 text-white shadow hover:bg-teal-700": variant === 'default',
            "bg-slate-800 text-white shadow hover:bg-slate-900": variant === 'secondary',
            "border border-slate-200 bg-transparent hover:bg-slate-100 text-slate-900": variant === 'outline',
            "hover:bg-slate-100 text-slate-900": variant === 'ghost',
            "bg-red-500 text-white shadow-sm hover:bg-red-600": variant === 'destructive',
            "h-9 px-4 py-2": size === 'default',
            "h-8 rounded-md px-3 text-xs": size === 'sm',
            "h-10 rounded-md px-8": size === 'lg',
            "h-9 w-9": size === 'icon',
          },
          className
        )}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";
