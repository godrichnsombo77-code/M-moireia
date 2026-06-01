import { Shield, AlertTriangle, AlertOctagon, Siren } from "lucide-react";

interface AlertLevelIndicatorProps {
  level: 0 | 1 | 2 | 3 | 4;
  label: string;
  description: string;
}

const levelConfig = {
  0: {
    icon: Shield,
    bgColor: "bg-[hsl(var(--success))]/10",
    borderColor: "border-[hsl(var(--success))]/30",
    textColor: "text-[hsl(var(--success))]",
    iconColor: "text-[hsl(var(--success))]",
  },
  1: {
    icon: Shield,
    bgColor: "bg-yellow-500/10",
    borderColor: "border-yellow-500/30",
    textColor: "text-yellow-400",
    iconColor: "text-yellow-400",
  },
  2: {
    icon: AlertTriangle,
    bgColor: "bg-orange-500/10",
    borderColor: "border-orange-500/30",
    textColor: "text-orange-400",
    iconColor: "text-orange-400",
  },
  3: {
    icon: AlertOctagon,
    bgColor: "bg-[hsl(var(--danger))]/10",
    borderColor: "border-[hsl(var(--danger))]/30",
    textColor: "text-[hsl(var(--danger))]",
    iconColor: "text-[hsl(var(--danger))]",
  },
  4: {
    icon: Siren,
    bgColor: "bg-[hsl(var(--critical))]/20",
    borderColor: "border-[hsl(var(--critical))]/50",
    textColor: "text-[hsl(var(--critical))]",
    iconColor: "text-[hsl(var(--critical))]",
    animate: true,
  },
};

export function AlertLevelIndicator({ level, label, description }: AlertLevelIndicatorProps) {
  const config = levelConfig[level];
  const Icon = config.icon;

  return (
    <div
      className={`
        flex items-center gap-4 p-4 rounded-xl border
        ${config.bgColor} ${config.borderColor}
        ${"animate" in config && config.animate ? "animate-pulse" : ""}
      `}
    >
      <div className={`p-3 rounded-lg ${config.bgColor}`}>
        <Icon className={`w-8 h-8 ${config.iconColor}`} />
      </div>
      <div>
        <div className="flex items-center gap-2">
          <span className={`text-lg font-bold ${config.textColor}`}>Niveau {level}</span>
          <span className={`px-2 py-0.5 rounded text-xs font-semibold ${config.bgColor} ${config.textColor}`}>
            {label}
          </span>
        </div>
        <p className="text-sm text-[hsl(var(--foreground-muted))]">{description}</p>
      </div>
    </div>
  );
}
