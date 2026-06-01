import { AlertTriangle, Clock, ArrowRight } from "lucide-react";

interface Alert {
  id: number;
  timestamp: string;
  priority: number;
  message: string;
  camera: string;
}

const recentAlerts: Alert[] = [
  { id: 1, timestamp: "14:32:15", priority: 3, message: "Arme a feu detectee", camera: "Camera 2" },
  { id: 2, timestamp: "14:25:30", priority: 2, message: "Violence detectee", camera: "Camera 1" },
  { id: 3, timestamp: "14:20:00", priority: 1, message: "Personne en zone restreinte", camera: "Camera 3" },
];

const priorityColors: Record<number, string> = {
  1: "bg-yellow-500",
  2: "bg-orange-500",
  3: "bg-red-500",
  4: "bg-red-600",
};

export function RecentAlerts() {
  return (
    <div className="bg-[hsl(var(--card))] rounded-xl border border-[hsl(var(--border))] p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 text-[hsl(var(--warning))]" />
          Alertes recentes
        </h3>
        <button className="flex items-center gap-1 text-sm text-[hsl(var(--primary))] hover:underline">
          Voir tout <ArrowRight className="w-4 h-4" />
        </button>
      </div>

      <div className="space-y-3">
        {recentAlerts.map((alert) => (
          <div
            key={alert.id}
            className="flex items-center gap-4 p-3 rounded-lg bg-[hsl(var(--background-secondary))] hover:bg-[hsl(var(--background-tertiary))] transition-colors"
          >
            <div className={`w-2 h-2 rounded-full ${priorityColors[alert.priority]}`} />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate">{alert.message}</p>
              <p className="text-xs text-[hsl(var(--foreground-muted))]">{alert.camera}</p>
            </div>
            <div className="flex items-center gap-1 text-xs text-[hsl(var(--foreground-muted))]">
              <Clock className="w-3 h-3" />
              {alert.timestamp}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
