"use client";

import { Activity, AlertTriangle, Camera, Shield, TrendingUp, Users } from "lucide-react";
import { StatCard } from "@/components/ui/stat-card";
import { AlertLevelIndicator } from "@/components/ui/alert-level-indicator";
import { RecentAlerts } from "@/components/ui/recent-alerts";

// Mock data - in production, this would come from the API
const stats = {
  cameras: { value: 4, label: "Cameras actives", trend: "+1 cette semaine" },
  detections: { value: 127, label: "Detections aujourd'hui", trend: "+12% vs hier" },
  alerts: { value: 8, label: "Alertes critiques", trend: "3 non traitees" },
  persons: { value: 45, label: "Personnes detectees", trend: "Derniere heure" },
};

export function DashboardView() {
  return (
    <div className="space-y-6">
      {/* Current Alert Level */}
      <AlertLevelIndicator level={1} label="MODERE" description="Activite normale detectee" />

      {/* Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={Camera}
          value={stats.cameras.value}
          label={stats.cameras.label}
          trend={stats.cameras.trend}
          color="primary"
        />
        <StatCard
          icon={Activity}
          value={stats.detections.value}
          label={stats.detections.label}
          trend={stats.detections.trend}
          color="blue"
        />
        <StatCard
          icon={AlertTriangle}
          value={stats.alerts.value}
          label={stats.alerts.label}
          trend={stats.alerts.trend}
          color="warning"
        />
        <StatCard
          icon={Users}
          value={stats.persons.value}
          label={stats.persons.label}
          trend={stats.persons.trend}
          color="purple"
        />
      </div>

      {/* Main content grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Detection Summary */}
        <div className="lg:col-span-2 bg-[hsl(var(--card))] rounded-xl border border-[hsl(var(--border))] p-6">
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Shield className="w-5 h-5 text-[hsl(var(--primary))]" />
            Resume des detections
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <DetectionStat label="Personnes" count={45} percentage={65} color="primary" />
            <DetectionStat label="Violence" count={3} percentage={4} color="danger" />
            <DetectionStat label="Armes a feu" count={1} percentage={1} color="critical" />
            <DetectionStat label="Couteaux" count={2} percentage={3} color="warning" />
          </div>
        </div>

        {/* System Status */}
        <div className="bg-[hsl(var(--card))] rounded-xl border border-[hsl(var(--border))] p-6">
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-[hsl(var(--primary))]" />
            Etat du systeme
          </h3>
          <div className="space-y-4">
            <SystemStatus label="API FastAPI" status="online" />
            <SystemStatus label="Modele YOLO" status="online" />
            <SystemStatus label="Qwen AI" status="online" />
            <SystemStatus label="Base de donnees" status="online" />
          </div>
        </div>
      </div>

      {/* Recent Alerts */}
      <RecentAlerts />
    </div>
  );
}

function DetectionStat({ label, count, percentage, color }: { label: string; count: number; percentage: number; color: string }) {
  const colorClasses: Record<string, string> = {
    primary: "bg-[hsl(var(--primary))]",
    danger: "bg-[hsl(var(--danger))]",
    critical: "bg-[hsl(var(--critical))]",
    warning: "bg-[hsl(var(--warning))]",
  };

  return (
    <div className="text-center">
      <div className="text-2xl font-bold">{count}</div>
      <div className="text-sm text-[hsl(var(--foreground-muted))] mb-2">{label}</div>
      <div className="h-2 bg-[hsl(var(--background-tertiary))] rounded-full overflow-hidden">
        <div className={`h-full ${colorClasses[color]} rounded-full transition-all duration-500`} style={{ width: `${percentage}%` }} />
      </div>
    </div>
  );
}

function SystemStatus({ label, status }: { label: string; status: "online" | "offline" | "warning" }) {
  const statusColors = {
    online: "bg-[hsl(var(--success))]",
    offline: "bg-[hsl(var(--danger))]",
    warning: "bg-[hsl(var(--warning))]",
  };

  return (
    <div className="flex items-center justify-between">
      <span className="text-sm">{label}</span>
      <div className="flex items-center gap-2">
        <span className={`w-2 h-2 rounded-full ${statusColors[status]}`} />
        <span className="text-xs text-[hsl(var(--foreground-muted))] capitalize">{status}</span>
      </div>
    </div>
  );
}
