"use client";

import { useState } from "react";
import { Save, RefreshCw, Wifi, Database, Cpu, Volume2 } from "lucide-react";

export function SettingsView() {
  const [threshold, setThreshold] = useState(0.5);
  const [voiceAlerts, setVoiceAlerts] = useState(true);
  const [autoRecord, setAutoRecord] = useState(true);
  const [recordDuration, setRecordDuration] = useState(10);

  return (
    <div className="max-w-4xl space-y-6">
      {/* Detection Settings */}
      <SettingsSection title="Detection" icon={Cpu}>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-2">
              Seuil de confiance: {(threshold * 100).toFixed(0)}%
            </label>
            <input
              type="range"
              min="0.1"
              max="0.9"
              step="0.05"
              value={threshold}
              onChange={(e) => setThreshold(parseFloat(e.target.value))}
              className="w-full h-2 bg-[hsl(var(--background-tertiary))] rounded-lg appearance-none cursor-pointer accent-[hsl(var(--primary))]"
            />
            <p className="text-xs text-[hsl(var(--foreground-muted))] mt-1">
              Un seuil plus bas detecte plus d&apos;objets mais peut generer des faux positifs
            </p>
          </div>
        </div>
      </SettingsSection>

      {/* Alert Settings */}
      <SettingsSection title="Alertes" icon={Volume2}>
        <div className="space-y-4">
          <ToggleSetting
            label="Alertes vocales"
            description="Annonces vocales lors des detections"
            checked={voiceAlerts}
            onChange={setVoiceAlerts}
          />
          <ToggleSetting
            label="Enregistrement automatique"
            description="Sauvegarder automatiquement les preuves"
            checked={autoRecord}
            onChange={setAutoRecord}
          />
          {autoRecord && (
            <div>
              <label className="block text-sm font-medium mb-2">
                Duree d&apos;enregistrement: {recordDuration}s
              </label>
              <input
                type="range"
                min="5"
                max="60"
                step="5"
                value={recordDuration}
                onChange={(e) => setRecordDuration(parseInt(e.target.value))}
                className="w-full h-2 bg-[hsl(var(--background-tertiary))] rounded-lg appearance-none cursor-pointer accent-[hsl(var(--primary))]"
              />
            </div>
          )}
        </div>
      </SettingsSection>

      {/* Connection Settings */}
      <SettingsSection title="Connexions" icon={Wifi}>
        <div className="space-y-3">
          <ConnectionStatus label="API FastAPI" url="http://localhost:8000" status="connected" />
          <ConnectionStatus label="Base de donnees SQLite" url="surveillance.db" status="connected" />
          <ConnectionStatus label="Qwen AI (DashScope)" url="dashscope-intl.aliyuncs.com" status="connected" />
        </div>
      </SettingsSection>

      {/* Database Settings */}
      <SettingsSection title="Base de donnees" icon={Database}>
        <div className="flex flex-wrap gap-3">
          <button className="flex items-center gap-2 px-4 py-2 bg-[hsl(var(--background-tertiary))] rounded-lg text-sm hover:bg-[hsl(var(--border))] transition-colors">
            <RefreshCw className="w-4 h-4" />
            Reinitialiser les statistiques
          </button>
          <button className="flex items-center gap-2 px-4 py-2 bg-[hsl(var(--danger))]/10 text-[hsl(var(--danger))] rounded-lg text-sm hover:bg-[hsl(var(--danger))]/20 transition-colors">
            <Database className="w-4 h-4" />
            Vider les alertes
          </button>
        </div>
      </SettingsSection>

      {/* Save button */}
      <div className="flex justify-end">
        <button className="flex items-center gap-2 px-6 py-2.5 bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] rounded-lg font-medium hover:opacity-90 transition-opacity">
          <Save className="w-4 h-4" />
          Sauvegarder les parametres
        </button>
      </div>
    </div>
  );
}

function SettingsSection({ title, icon: Icon, children }: { title: string; icon: typeof Cpu; children: React.ReactNode }) {
  return (
    <div className="bg-[hsl(var(--card))] rounded-xl border border-[hsl(var(--border))] p-6">
      <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
        <Icon className="w-5 h-5 text-[hsl(var(--primary))]" />
        {title}
      </h3>
      {children}
    </div>
  );
}

function ToggleSetting({ label, description, checked, onChange }: { label: string; description: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <div className="flex items-center justify-between">
      <div>
        <div className="font-medium text-sm">{label}</div>
        <div className="text-xs text-[hsl(var(--foreground-muted))]">{description}</div>
      </div>
      <button
        onClick={() => onChange(!checked)}
        className={`relative w-11 h-6 rounded-full transition-colors ${checked ? "bg-[hsl(var(--primary))]" : "bg-[hsl(var(--background-tertiary))]"}`}
      >
        <span className={`absolute top-1 left-1 w-4 h-4 rounded-full bg-white transition-transform ${checked ? "translate-x-5" : ""}`} />
      </button>
    </div>
  );
}

function ConnectionStatus({ label, url, status }: { label: string; url: string; status: "connected" | "disconnected" }) {
  return (
    <div className="flex items-center justify-between p-3 bg-[hsl(var(--background-secondary))] rounded-lg">
      <div>
        <div className="font-medium text-sm">{label}</div>
        <div className="text-xs text-[hsl(var(--foreground-muted))] font-mono">{url}</div>
      </div>
      <div className="flex items-center gap-2">
        <span className={`w-2 h-2 rounded-full ${status === "connected" ? "bg-[hsl(var(--success))]" : "bg-[hsl(var(--danger))]"}`} />
        <span className="text-xs">{status === "connected" ? "Connecte" : "Deconnecte"}</span>
      </div>
    </div>
  );
}
