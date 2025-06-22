
import { useState } from "react";
import { MapComponent } from "@/components/MapComponent";
import { Sidebar } from "@/components/Sidebar";
import { Header } from "@/components/Header";
import { ThemeProvider } from "@/components/ThemeProvider";

const Index = () => {
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

  return (
    <ThemeProvider>
      <div className="min-h-screen bg-background flex flex-col w-full overflow-hidden">
        <Header 
          onToggleSidebar={() => setIsSidebarOpen(!isSidebarOpen)}
          isSidebarOpen={isSidebarOpen}
        />
        
        <div className="flex flex-1 relative overflow-hidden">
          <Sidebar isOpen={isSidebarOpen} />
          
          <main className={`flex-1 transition-all duration-300 overflow-hidden ${
            isSidebarOpen ? 'lg:ml-80' : 'ml-0'
          }`}>
            <MapComponent />
          </main>
        </div>
      </div>
    </ThemeProvider>
  );
};

export default Index;
