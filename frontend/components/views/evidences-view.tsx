"use client";

import { useState } from "react";
import { Image, Video, Calendar, Download, Trash2, Eye } from "lucide-react";

interface Evidence {
  id: number;
  type: "image" | "video";
  timestamp: string;
  camera: string;
  alertType: string;
  thumbnail: string;
}

// Mock data
const mockEvidences: Evidence[] = [
  { id: 1, type: "image", timestamp: "2024-01-15 14:32:15", camera: "Camera 1", alertType: "Violence", thumbnail: "" },
  { id: 2, type: "video", timestamp: "2024-01-15 14:30:00", camera: "Camera 2", alertType: "Arme detectee", thumbnail: "" },
  { id: 3, type: "image", timestamp: "2024-01-15 14:25:30", camera: "Camera 1", alertType: "Violence", thumbnail: "" },
  { id: 4, type: "image", timestamp: "2024-01-15 14:20:00", camera: "Camera 3", alertType: "Personne", thumbnail: "" },
  { id: 5, type: "video", timestamp: "2024-01-15 14:15:00", camera: "Camera 1", alertType: "Violence", thumbnail: "" },
  { id: 6, type: "image", timestamp: "2024-01-15 14:10:00", camera: "Camera 2", alertType: "Couteau", thumbnail: "" },
];

export function EvidencesView() {
  const [filterType, setFilterType] = useState<"all" | "image" | "video">("all");
  const [selectedEvidence, setSelectedEvidence] = useState<Evidence | null>(null);

  const filteredEvidences = mockEvidences.filter((e) => {
    if (filterType === "all") return true;
    return e.type === filterType;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold">Galerie des preuves</h2>
          <p className="text-sm text-[hsl(var(--foreground-muted))]">{mockEvidences.length} fichiers enregistres</p>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-2 p-1 bg-[hsl(var(--background-secondary))] rounded-lg border border-[hsl(var(--border))]">
          {(["all", "image", "video"] as const).map((type) => (
            <button
              key={type}
              onClick={() => setFilterType(type)}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-all ${
                filterType === type
                  ? "bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))]"
                  : "text-[hsl(var(--foreground-muted))] hover:text-[hsl(var(--foreground))]"
              }`}
            >
              {type === "all" ? "Tous" : type === "image" ? <><Image className="w-4 h-4" /> Images</> : <><Video className="w-4 h-4" /> Videos</>}
            </button>
          ))}
        </div>
      </div>

      {/* Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {filteredEvidences.map((evidence) => (
          <div
            key={evidence.id}
            className="group bg-[hsl(var(--card))] rounded-xl border border-[hsl(var(--border))] overflow-hidden hover:border-[hsl(var(--primary))] transition-all"
          >
            {/* Thumbnail */}
            <div className="relative aspect-video bg-[hsl(var(--background))] flex items-center justify-center">
              {evidence.type === "image" ? (
                <Image className="w-12 h-12 text-[hsl(var(--foreground-muted))] opacity-30" />
              ) : (
                <Video className="w-12 h-12 text-[hsl(var(--foreground-muted))] opacity-30" />
              )}

              {/* Type badge */}
              <div className={`absolute top-2 left-2 px-2 py-0.5 rounded text-xs font-medium ${
                evidence.type === "image" 
                  ? "bg-blue-500/20 text-blue-400" 
                  : "bg-purple-500/20 text-purple-400"
              }`}>
                {evidence.type === "image" ? "IMAGE" : "VIDEO"}
              </div>

              {/* Hover overlay */}
              <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
                <button
                  onClick={() => setSelectedEvidence(evidence)}
                  className="p-2 bg-white/20 rounded-lg hover:bg-white/30 transition-colors"
                >
                  <Eye className="w-5 h-5" />
                </button>
                <button className="p-2 bg-white/20 rounded-lg hover:bg-white/30 transition-colors">
                  <Download className="w-5 h-5" />
                </button>
                <button className="p-2 bg-red-500/30 rounded-lg hover:bg-red-500/50 transition-colors">
                  <Trash2 className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Info */}
            <div className="p-3 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">{evidence.alertType}</span>
                <span className="text-xs text-[hsl(var(--foreground-muted))]">{evidence.camera}</span>
              </div>
              <div className="flex items-center gap-1 text-xs text-[hsl(var(--foreground-muted))]">
                <Calendar className="w-3 h-3" />
                {evidence.timestamp}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Empty state */}
      {filteredEvidences.length === 0 && (
        <div className="text-center py-12">
          <Image className="w-16 h-16 mx-auto mb-4 text-[hsl(var(--foreground-muted))] opacity-30" />
          <p className="text-[hsl(var(--foreground-muted))]">Aucune preuve trouvee</p>
        </div>
      )}

      {/* Preview Modal */}
      {selectedEvidence && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4" onClick={() => setSelectedEvidence(null)}>
          <div className="bg-[hsl(var(--card))] rounded-xl max-w-4xl w-full max-h-[90vh] overflow-hidden" onClick={(e) => e.stopPropagation()}>
            <div className="aspect-video bg-[hsl(var(--background))] flex items-center justify-center">
              {selectedEvidence.type === "image" ? (
                <Image className="w-24 h-24 text-[hsl(var(--foreground-muted))] opacity-30" />
              ) : (
                <Video className="w-24 h-24 text-[hsl(var(--foreground-muted))] opacity-30" />
              )}
            </div>
            <div className="p-4 border-t border-[hsl(var(--border))]">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-semibold">{selectedEvidence.alertType}</h3>
                  <p className="text-sm text-[hsl(var(--foreground-muted))]">{selectedEvidence.camera} - {selectedEvidence.timestamp}</p>
                </div>
                <div className="flex gap-2">
                  <button className="px-4 py-2 bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] rounded-lg text-sm font-medium">
                    Telecharger
                  </button>
                  <button onClick={() => setSelectedEvidence(null)} className="px-4 py-2 bg-[hsl(var(--background-secondary))] rounded-lg text-sm font-medium">
                    Fermer
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
