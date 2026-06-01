"use client";

import { Bell, Clock, Menu } from "lucide-react";
import { useEffect, useState } from "react";
import type { ViewType } from "@/app/page";

interface HeaderProps {
  currentView: ViewType;
  onMenuClick: () => void;
  isMobile: boolean;
}

const viewTitles: Record<ViewType, string> = {
  dashboard: "Tableau de bord",
  live: "Surveillance en direct",
  alerts: "Journal des alertes",
  evidences: "Galerie des preuves",
  settings: "Parametres",
};

export function Header({ currentView, onMenuClick, isMobile }: HeaderProps) {
  const [time, setTime] = useState<string>("");

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setTime(now.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit", second: "2-digit" }));
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="flex items-center justify-between px-4 md:px-6 py-4 bg-[hsl(var(--background-secondary))] border-b border-[hsl(var(--border))]">
      <div className="flex items-center gap-3">
        {isMobile && (
          <button
            onClick={onMenuClick}
            className="p-2 -ml-2 rounded-lg hover:bg-[hsl(var(--background-tertiary))] transition-colors"
          >
            <Menu className="w-5 h-5" />
          </button>
        )}
        <div>
          <h1 className="text-lg md:text-2xl font-bold">{viewTitles[currentView]}</h1>
          <p className="text-xs md:text-sm text-[hsl(var(--foreground-muted))] hidden sm:block">
            Systeme de surveillance intelligente
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2 md:gap-4">
        {/* Live time */}
        <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[hsl(var(--background-tertiary))] border border-[hsl(var(--border))]">
          <Clock className="w-4 h-4 text-[hsl(var(--foreground-muted))]" />
          <span className="font-mono text-sm">{time}</span>
        </div>

        {/* Status indicator */}
        <div className="flex items-center gap-2 px-2 md:px-3 py-1.5 rounded-lg bg-[hsl(var(--background-tertiary))] border border-[hsl(var(--border))]">
          <span className="w-2 h-2 rounded-full bg-[hsl(var(--success))] animate-pulse-live" />
          <span className="text-xs md:text-sm text-[hsl(var(--success))]">En ligne</span>
        </div>

        {/* Notifications */}
        <button className="relative p-2 rounded-lg hover:bg-[hsl(var(--background-tertiary))] transition-colors">
          <Bell className="w-5 h-5" />
          <span className="absolute top-1 right-1 w-2 h-2 rounded-full bg-[hsl(var(--danger))]" />
        </button>
      </div>
    </header>
  );
}
