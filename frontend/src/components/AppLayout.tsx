import { AppSidebar } from "@/components/AppSidebar";
import { AuroraBackground } from "@/components/ui/AuroraBackground";
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <SidebarProvider>
      <AuroraBackground />
      <div className="min-h-screen flex w-full relative z-10">
        <AppSidebar />
        <div className="flex-1 flex flex-col min-h-screen min-w-0">
          <header className="h-14 border-b border-border/40 flex items-center px-4 gap-3 shrink-0 glass sticky top-0 z-20">
            <SidebarTrigger aria-label="Toggle navigation sidebar" />
            <span className="sr-only" aria-live="polite">NutriFlavorOS application navigation</span>
          </header>
          <main id="main-content" tabIndex={-1} className="flex-1 overflow-auto p-4 sm:p-6 focus:outline-none">{children}</main>
        </div>
      </div>
    </SidebarProvider>
  );
}
