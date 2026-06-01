"use client";

import {
  LayoutDashboard,
  Video,
  AlertTriangle,
  FolderOpen,
  Settings,
  X,
  Shield,
} from "lucide-react";
import type { ViewType } from "@/app/page";

interface SidebarProps {
  currentView: ViewType;
  onViewChange: (view: ViewType) => void;
  isOpen: boolean;
  isMobile: boolean;
  onClose: () => void;
}

const navItems = [
  { id: "dashboard" as ViewType, label: "Tableau de bord", icon: LayoutDashboard },
  { id: "live" as ViewType, label: "Surveillance Live", icon: Video },
  { id: "alerts" as ViewType, label: "Alertes", icon: AlertTriangle },
  { id: "evidences" as ViewType, label: "Preuves", icon: FolderOpen },
  { id: "settings" as ViewType, label: "Parametres", icon: Settings },
];

export function Sidebar({ currentView, onViewChange, isOpen, isMobile, onClose }: SidebarProps) {
  if (isMobile && !isOpen) {
    return null;
  }

  return (
    <aside
      className={`
        flex flex-col bg-[hsl(var(--background-secondary))] border-r border-[hsl(var(--border))]
        transition-all duration-300 ease-in-out
        ${isMobile 
          ? "fixed inset-y-0 left-0 z-50 w-64" 
          : "w-64"
        }
      `}
    >
      {/* Logo */}
      <div className="flex items-center justify-between px-4 py-5 border-b border-[hsl(var(--border))]">
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-[hsl(var(--primary))]">
            <Shield className="w-6 h-6 text-[hsl(var(--primary-foreground))]" />
          </div>
          <div className="flex flex-col">
            <span className="font-bold text-lg tracking-tight">M-MOIREIA</span>
            <span className="text-xs text-[hsl(var(--foreground-muted))]">Surveillance IA</span>
          </div>
        </div>
        {isMobile && (
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-[hsl(var(--background-tertiary))] transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-4">
        <ul className="space-y-1 px-2">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = currentView === item.id;
            return (
              <li key={item.id}>
                <button
                  onClick={() => onViewChange(item.id)}
                  className={`
                    w-full flex items-center gap-3 px-3 py-2.5 rounded-lg
                    transition-all duration-200
                    ${isActive
                      ? "bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))]"
                      : "text-[hsl(var(--foreground-muted))] hover:text-[hsl(var(--foreground))] hover:bg-[hsl(var(--background-tertiary))]"
                    }
                  `}
                >
                  <Icon className="w-5 h-5 flex-shrink-0" />
                  <span className="text-sm font-medium">{item.label}</span>
                </button>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Version info */}
      <div className="p-4 border-t border-[hsl(var(--border))]">
        <div className="text-xs text-[hsl(var(--foreground-muted))] text-center">
          Version 2.0 - Next.js
        </div>
      </div>
    </aside>
  );
}
