"use client";

import { useState, useEffect } from "react";
import { Sidebar } from "@/components/sidebar";
import { Header } from "@/components/header";
import { DashboardView } from "@/components/views/dashboard-view";
import { LiveView } from "@/components/views/live-view";
import { AlertsView } from "@/components/views/alerts-view";
import { EvidencesView } from "@/components/views/evidences-view";
import { SettingsView } from "@/components/views/settings-view";

export type ViewType = "dashboard" | "live" | "alerts" | "evidences" | "settings";

export default function Home() {
  const [currentView, setCurrentView] = useState<ViewType>("dashboard");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768);
      if (window.innerWidth >= 768) {
        setSidebarOpen(true);
      }
    };
    checkMobile();
    window.addEventListener("resize", checkMobile);
    return () => window.removeEventListener("resize", checkMobile);
  }, []);

  const handleViewChange = (view: ViewType) => {
    setCurrentView(view);
    if (isMobile) {
      setSidebarOpen(false);
    }
  };

  const renderView = () => {
    switch (currentView) {
      case "dashboard":
        return <DashboardView />;
      case "live":
        return <LiveView />;
      case "alerts":
        return <AlertsView />;
      case "evidences":
        return <EvidencesView />;
      case "settings":
        return <SettingsView />;
      default:
        return <DashboardView />;
    }
  };

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Mobile overlay */}
      {isMobile && sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <Sidebar
        currentView={currentView}
        onViewChange={handleViewChange}
        isOpen={sidebarOpen}
        isMobile={isMobile}
        onClose={() => setSidebarOpen(false)}
      />

      <div className="flex flex-col flex-1 overflow-hidden">
        <Header
          currentView={currentView}
          onMenuClick={() => setSidebarOpen(!sidebarOpen)}
          isMobile={isMobile}
        />
        <main className="flex-1 overflow-auto p-4 md:p-6">
          {renderView()}
        </main>
      </div>
    </div>
  );
}
