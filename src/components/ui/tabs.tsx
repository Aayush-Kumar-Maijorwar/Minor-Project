import React from 'react';
import { cn } from '@/lib/utils';

export const Tabs = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn("w-full", className)} {...props} />
);

export const TabsList = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn("inline-flex h-10 items-center justify-center rounded-md bg-slate-100 p-1 text-slate-500", className)} {...props} />
);

export const TabsTrigger = ({ 
  className, active, ...props 
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { active?: boolean }) => (
  <button
    className={cn(
      "inline-flex items-center justify-center whitespace-nowrap rounded-sm px-3 py-1.5 text-sm font-medium ring-offset-white transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
      active ? "bg-white text-slate-950 shadow-sm" : "hover:text-slate-900",
      className
    )}
    {...props}
  />
);

export const TabsContent = ({ 
  className, active, ...props 
}: React.HTMLAttributes<HTMLDivElement> & { active?: boolean }) => {
  if (!active) return null;
  return (
    <div
      className={cn("mt-2 ring-offset-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:ring-offset-2", className)}
      {...props}
    />
  );
};
