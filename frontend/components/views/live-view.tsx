"use client";

import { useState } from "react";
import { Camera, Play, Pause, Settings2, Maximize2, AlertCircle } from "lucide-react";

type SourceType = "webcam" | "rtsp" | "file";

export function LiveView() {
  const [isStreaming, setIsStreaming] = useState(false);
  const [sourceType, setSourceType] = useState<SourceType>("webcam");
  const [rtspUrl, setRtspUrl] = useState("");

  return (
    <div className="space-y-6">
      {/* Source Selection */}
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-2 p-1 bg-[hsl(var(--background-secondary))] rounded-lg border border-[hsl(var(--border))]">
          {(["webcam", "rtsp", "file"] as SourceType[]).map((type) => (
            <button
              key={type}
              onClick={() => setSourceType(type)}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${
                sourceType === type
                  ? "bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))]"
                  : "text-[hsl(var(--foreground-muted))] hover:text-[hsl(var(--foreground))]"
              }`}
            >
              {type === "webcam" ? "Webcam" : type === "rtsp" ? "RTSP" : "Fichier"}
            </button>
          ))}
        </div>

        {sourceType === "rtsp" && (
          <input
            type="text"
            placeholder="rtsp://192.168.1.100:554/stream"
            value={rtspUrl}
            onChange={(e) => setRtspUrl(e.target.value)}
            className="flex-1 min-w-64 px-4 py-2 bg-[hsl(var(--background-tertiary))] border border-[hsl(var(--border))] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[hsl(var(--primary))]"
          />
        )}

        <button
          onClick={() => setIsStreaming(!isStreaming)}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all ${
            isStreaming
              ? "bg-[hsl(var(--danger))] text-white"
              : "bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))]"
          }`}
        >
          {isStreaming ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
          {isStreaming ? "Arreter" : "Demarrer"}
        </button>
      </div>

      {/* Main Video Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Feed */}
        <div className="lg:col-span-2">
          <VideoFeed
            title="Flux principal"
            isMain
            isStreaming={isStreaming}
          />
        </div>

        {/* Side Panel */}
        <div className="space-y-4">
          {/* Detection Info */}
          <div className="bg-[hsl(var(--card))] rounded-xl border border-[hsl(var(--border))] p-4">
            <h3 className="font-semibold mb-3 flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-[hsl(var(--primary))]" />
              Detections en cours
            </h3>
            <div className="space-y-2">
              <DetectionItem label="Personnes" count={2} color="primary" />
              <DetectionItem label="Violence" count={0} color="success" />
              <DetectionItem label="Armes" count={0} color="success" />
            </div>
          </div>

          {/* AI Analysis */}
          <div className="bg-[hsl(var(--card))] rounded-xl border border-[hsl(var(--border))] p-4">
            <h3 className="font-semibold mb-3 flex items-center gap-2">
              <Settings2 className="w-4 h-4 text-[hsl(var(--primary))]" />
              Analyse Qwen AI
            </h3>
            <div className="text-sm text-[hsl(var(--foreground-muted))] italic">
              {isStreaming
                ? "Analyse en cours... Aucune menace detectee."
                : "Demarrez le flux pour activer l'analyse IA"}
            </div>
          </div>

          {/* Quick Stats */}
          <div className="bg-[hsl(var(--card))] rounded-xl border border-[hsl(var(--border))] p-4">
            <h3 className="font-semibold mb-3">Statistiques de session</h3>
            <div className="grid grid-cols-2 gap-3 text-center">
              <div className="p-2 bg-[hsl(var(--background-tertiary))] rounded-lg">
                <div className="text-lg font-bold">00:00:00</div>
                <div className="text-xs text-[hsl(var(--foreground-muted))]">Duree</div>
              </div>
              <div className="p-2 bg-[hsl(var(--background-tertiary))] rounded-lg">
                <div className="text-lg font-bold">0</div>
                <div className="text-xs text-[hsl(var(--foreground-muted))]">Alertes</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Camera Grid */}
      <div>
        <h3 className="font-semibold mb-4">Toutes les cameras</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <VideoFeed key={i} title={`Camera ${i}`} isStreaming={isStreaming && i === 1} />
          ))}
        </div>
      </div>
    </div>
  );
}

function VideoFeed({ title, isMain = false, isStreaming = false }: { title: string; isMain?: boolean; isStreaming?: boolean }) {
  return (
    <div className={`bg-[hsl(var(--card))] rounded-xl border border-[hsl(var(--border))] overflow-hidden ${isMain ? "" : ""}`}>
      <div className="relative aspect-video bg-[hsl(var(--background))] flex items-center justify-center">
        {isStreaming ? (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-[hsl(var(--foreground-muted))]">
              <Camera className="w-12 h-12 mx-auto mb-2 opacity-50" />
              <p className="text-sm">Flux video actif</p>
            </div>
            {/* Live indicator */}
            <div className="absolute top-3 left-3 flex items-center gap-2 px-2 py-1 bg-[hsl(var(--danger))] rounded text-xs font-medium">
              <span className="w-2 h-2 rounded-full bg-white animate-pulse" />
              LIVE
            </div>
          </div>
        ) : (
          <div className="text-[hsl(var(--foreground-muted))]">
            <Camera className="w-12 h-12 mx-auto mb-2 opacity-30" />
            <p className="text-sm">Hors ligne</p>
          </div>
        )}

        {/* Fullscreen button */}
        {isMain && (
          <button className="absolute top-3 right-3 p-2 bg-black/50 rounded-lg hover:bg-black/70 transition-colors">
            <Maximize2 className="w-4 h-4" />
          </button>
        )}
      </div>
      <div className="p-3 flex items-center justify-between">
        <span className="text-sm font-medium">{title}</span>
        <span className={`text-xs px-2 py-0.5 rounded ${isStreaming ? "bg-[hsl(var(--success))]/20 text-[hsl(var(--success))]" : "bg-[hsl(var(--foreground-muted))]/20 text-[hsl(var(--foreground-muted))]"}`}>
          {isStreaming ? "Actif" : "Inactif"}
        </span>
      </div>
    </div>
  );
}

function DetectionItem({ label, count, color }: { label: string; count: number; color: string }) {
  const colorClasses: Record<string, string> = {
    primary: "text-[hsl(var(--primary))]",
    success: "text-[hsl(var(--success))]",
    danger: "text-[hsl(var(--danger))]",
  };

  return (
    <div className="flex items-center justify-between py-1">
      <span className="text-sm text-[hsl(var(--foreground-muted))]">{label}</span>
      <span className={`font-mono font-bold ${colorClasses[color]}`}>{count}</span>
    </div>
  );
}
