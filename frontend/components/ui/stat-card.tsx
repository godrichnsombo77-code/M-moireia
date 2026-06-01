import { LucideIcon } from "lucide-react";

interface StatCardProps {
  icon: LucideIcon;
  value: number;
  label: string;
  trend?: string;
  color?: "primary" | "blue" | "warning" | "purple" | "danger";
}

const colorClasses = {
  primary: "bg-[hsl(var(--primary))]/10 text-[hsl(var(--primary))]",
  blue: "bg-blue-500/10 text-blue-400",
  warning: "bg-[hsl(var(--warning))]/10 text-[hsl(var(--warning))]",
  purple: "bg-purple-500/10 text-purple-400",
  danger: "bg-[hsl(var(--danger))]/10 text-[hsl(var(--danger))]",
};

export function StatCard({ icon: Icon, value, label, trend, color = "primary" }: StatCardProps) {
  return (
    <div className="bg-[hsl(var(--card))] rounded-xl border border-[hsl(var(--border))] p-4 hover:border-[hsl(var(--foreground-muted))]/30 transition-colors">
      <div className="flex items-start justify-between mb-3">
        <div className={`p-2 rounded-lg ${colorClasses[color]}`}>
          <Icon className="w-5 h-5" />
        </div>
      </div>
      <div className="text-3xl font-bold mb-1">{value}</div>
      <div className="text-sm text-[hsl(var(--foreground-muted))]">{label}</div>
      {trend && (
        <div className="text-xs text-[hsl(var(--foreground-muted))] mt-2 opacity-70">{trend}</div>
      )}
    </div>
  );
}
