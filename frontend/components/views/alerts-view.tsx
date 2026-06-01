"use client";

import { useState } from "react";
import { Search, Filter, AlertTriangle, AlertCircle, Info, XCircle } from "lucide-react";

type AlertPriority = 0 | 1 | 2 | 3 | 4;

interface Alert {
  id: number;
  timestamp: string;
  priority: AlertPriority;
  type: string;
  message: string;
  camera: string;
  resolved: boolean;
}

// Mock data
const mockAlerts: Alert[] = [
  { id: 1, timestamp: "2024-01-15 14:32:15", priority: 4, type: "URGENCE", message: "Violence detectee avec arme a feu", camera: "Camera 1", resolved: false },
  { id: 2, timestamp: "2024-01-15 14:30:00", priority: 3, type: "CRITIQUE", message: "Arme a feu detectee", camera: "Camera 2", resolved: false },
  { id: 3, timestamp: "2024-01-15 14:25:30", priority: 2, type: "ELEVE", message: "Violence detectee", camera: "Camera 1", resolved: true },
  { id: 4, timestamp: "2024-01-15 14:20:00", priority: 1, type: "MODERE", message: "Personne detectee dans zone restreinte", camera: "Camera 3", resolved: true },
  { id: 5, timestamp: "2024-01-15 14:15:00", priority: 0, type: "INFO", message: "Systeme operationnel", camera: "Systeme", resolved: true },
];

const priorityConfig: Record<AlertPriority, { label: string; color: string; bgColor: string; icon: typeof AlertTriangle }> = {
  0: { label: "INFO", color: "text-blue-400", bgColor: "bg-blue-400/10 border-blue-400/30", icon: Info },
  1: { label: "MODERE", color: "text-yellow-400", bgColor: "bg-yellow-400/10 border-yellow-400/30", icon: AlertCircle },
  2: { label: "ELEVE", color: "text-orange-400", bgColor: "bg-orange-400/10 border-orange-400/30", icon: AlertTriangle },
  3: { label: "CRITIQUE", color: "text-red-400", bgColor: "bg-red-400/10 border-red-400/30", icon: XCircle },
  4: { label: "URGENCE", color: "text-red-500", bgColor: "bg-red-500/10 border-red-500/30 animate-pulse", icon: XCircle },
};

export function AlertsView() {
  const [searchQuery, setSearchQuery] = useState("");
  const [filterPriority, setFilterPriority] = useState<AlertPriority | "all">("all");
  const [showResolved, setShowResolved] = useState(true);

  const filteredAlerts = mockAlerts.filter((alert) => {
    if (filterPriority !== "all" && alert.priority !== filterPriority) return false;
    if (!showResolved && alert.resolved) return false;
    if (searchQuery && !alert.message.toLowerCase().includes(searchQuery.toLowerCase())) return false;
    return true;
  });

  return (
    <div className="space-y-6">
      {/* Filters */}
      <div className="flex flex-wrap gap-4">
        {/* Search */}
        <div className="relative flex-1 min-w-64">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[hsl(var(--foreground-muted))]" />
          <input
            type="text"
            placeholder="Rechercher une alerte..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-[hsl(var(--background-secondary))] border border-[hsl(var(--border))] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[hsl(var(--primary))]"
          />
        </div>

        {/* Priority Filter */}
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-[hsl(var(--foreground-muted))]" />
          <select
            value={filterPriority}
            onChange={(e) => setFilterPriority(e.target.value === "all" ? "all" : Number(e.target.value) as AlertPriority)}
            className="px-3 py-2 bg-[hsl(var(--background-secondary))] border border-[hsl(var(--border))] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[hsl(var(--primary))]"
          >
            <option value="all">Toutes priorites</option>
            <option value="4">URGENCE</option>
            <option value="3">CRITIQUE</option>
            <option value="2">ELEVE</option>
            <option value="1">MODERE</option>
            <option value="0">INFO</option>
          </select>
        </div>

        {/* Show resolved toggle */}
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={showResolved}
            onChange={(e) => setShowResolved(e.target.checked)}
            className="w-4 h-4 rounded border-[hsl(var(--border))] bg-[hsl(var(--background-secondary))] accent-[hsl(var(--primary))]"
          />
          <span className="text-sm">Afficher resolues</span>
        </label>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {([4, 3, 2, 1, 0] as AlertPriority[]).map((priority) => {
          const config = priorityConfig[priority];
          const count = mockAlerts.filter((a) => a.priority === priority).length;
          return (
            <button
              key={priority}
              onClick={() => setFilterPriority(filterPriority === priority ? "all" : priority)}
              className={`p-3 rounded-lg border transition-all ${
                filterPriority === priority ? config.bgColor : "bg-[hsl(var(--card))] border-[hsl(var(--border))] hover:border-[hsl(var(--foreground-muted))]"
              }`}
            >
              <div className={`text-2xl font-bold ${config.color}`}>{count}</div>
              <div className="text-xs text-[hsl(var(--foreground-muted))]">{config.label}</div>
            </button>
          );
        })}
      </div>

      {/* Alerts List */}
      <div className="bg-[hsl(var(--card))] rounded-xl border border-[hsl(var(--border))] overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-[hsl(var(--border))] bg-[hsl(var(--background-secondary))]">
                <th className="text-left px-4 py-3 text-xs font-semibold text-[hsl(var(--foreground-muted))] uppercase tracking-wider">Priorite</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-[hsl(var(--foreground-muted))] uppercase tracking-wider">Horodatage</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-[hsl(var(--foreground-muted))] uppercase tracking-wider">Message</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-[hsl(var(--foreground-muted))] uppercase tracking-wider">Source</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-[hsl(var(--foreground-muted))] uppercase tracking-wider">Statut</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[hsl(var(--border))]">
              {filteredAlerts.map((alert) => {
                const config = priorityConfig[alert.priority];
                const Icon = config.icon;
                return (
                  <tr key={alert.id} className="hover:bg-[hsl(var(--background-secondary))] transition-colors">
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center gap-1.5 px-2 py-1 rounded text-xs font-medium ${config.bgColor} ${config.color} border`}>
                        <Icon className="w-3 h-3" />
                        {config.label}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-mono text-sm text-[hsl(var(--foreground-muted))]">{alert.timestamp}</td>
                    <td className="px-4 py-3 text-sm">{alert.message}</td>
                    <td className="px-4 py-3 text-sm text-[hsl(var(--foreground-muted))]">{alert.camera}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex px-2 py-1 rounded text-xs font-medium ${
                        alert.resolved
                          ? "bg-[hsl(var(--success))]/10 text-[hsl(var(--success))]"
                          : "bg-[hsl(var(--warning))]/10 text-[hsl(var(--warning))]"
                      }`}>
                        {alert.resolved ? "Resolue" : "En attente"}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
