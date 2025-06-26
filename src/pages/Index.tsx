import { useState, useEffect } from "react";
import { MapComponent } from "@/components/MapComponent";
import { Sidebar } from "@/components/Sidebar";
import { Header } from "@/components/Header";
import { ThemeProvider } from "@/components/ThemeProvider";
import { Link } from 'react-router-dom';

// NOTE: The /admin page is intentionally not linked from anywhere in the main UI. Access it directly via /admin.

const Index = () => {
  // Sidebar closed by default on mobile
  const [isSidebarOpen, setIsSidebarOpen] = useState(() => {
    if (typeof window !== 'undefined') {
      return window.innerWidth >= 1024; // lg breakpoint
    }
    return true;
  });

  // Update sidebar state on resize
  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth < 1024) {
        setIsSidebarOpen(false);
      } else {
        setIsSidebarOpen(true);
      }
    };
    window.addEventListener('resize', handleResize);
    // Listen for custom closeSidebar event
    const handleCloseSidebar = () => setIsSidebarOpen(false);
    window.addEventListener('closeSidebar', handleCloseSidebar);
    return () => {
      window.removeEventListener('resize', handleResize);
      window.removeEventListener('closeSidebar', handleCloseSidebar);
    };
  }, []);

  return (
    <ThemeProvider>
      <div className="min-h-screen bg-background flex flex-col w-full overflow-hidden">
        <Header 
          onToggleSidebar={() => setIsSidebarOpen(!isSidebarOpen)}
          isSidebarOpen={isSidebarOpen}
        />
        
        <div className="flex flex-1 relative overflow-hidden">
          {/* Sidebar - positioned properly for both mobile and desktop */}
          <div className={`${
            isSidebarOpen 
              ? 'fixed inset-0 z-50 lg:static lg:z-auto lg:w-80' 
              : 'hidden lg:block lg:w-80'
          }`}>
            <Sidebar isOpen={isSidebarOpen} />
          </div>
          
          {/* Main content area */}
          <main className={`flex-1 transition-all duration-300 overflow-hidden ${
            isSidebarOpen ? 'lg:ml-80' : 'ml-0'
          } min-h-[calc(100vh-4rem)] relative z-0`}
            style={{ minHeight: 'calc(100vh - 4rem)' }}
          >
            <MapComponent />
          </main>
        </div>
      </div>
    </ThemeProvider>
  );
};

export default Index;
