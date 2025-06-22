
import { Button } from "@/components/ui/button";
import { useTheme } from "@/components/ThemeProvider";
import { Menu, Route, Settings } from "lucide-react";

interface HeaderProps {
  onToggleSidebar: () => void;
  isSidebarOpen: boolean;
}

export const Header: React.FC<HeaderProps> = ({ onToggleSidebar, isSidebarOpen }) => {
  const { theme, toggleTheme } = useTheme();

  return (
    <header className="bg-background border-b border-border px-4 py-3 flex items-center justify-between sticky top-0 z-50">
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="sm"
          onClick={onToggleSidebar}
          className="lg:hidden"
        >
          <Menu className="h-5 w-5" />
        </Button>
        
        <div className="flex items-center gap-2">
          <div className="bg-gradient-to-r from-blue-600 to-purple-600 p-2 rounded-lg">
            <Route className="h-6 w-6 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
              SmartRoute AI
            </h1>
            <p className="text-xs text-muted-foreground">Road Health-Aware Routing</p>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <Button
          variant="ghost"
          size="sm"
          onClick={toggleTheme}
          className="hidden sm:flex"
        >
          {theme === "light" ? "🌙" : "☀️"}
        </Button>
        
        <Button variant="ghost" size="sm" className="hidden sm:flex">
          <Settings className="h-4 w-4" />
        </Button>
      </div>
    </header>
  );
};
