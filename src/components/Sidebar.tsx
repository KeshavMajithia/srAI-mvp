import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { MapPin, Route, Image, Plus, X, Upload, Loader2 } from "lucide-react";
import { useRouteStore } from "@/store/routeStore";
import { toast } from "@/hooks/use-toast";

interface SidebarProps {
  isOpen: boolean;
}

export const Sidebar: React.FC<SidebarProps> = ({ isOpen }) => {
  const {
    startCoords,
    endCoords,
    isSelecting,
    routeData,
    roadConditions,
    isLoading,
    setSelecting,
    resetRoute,
    generateRoute,
    addRoadCondition
  } = useRouteStore();

  const [uploadedImages, setUploadedImages] = useState<File[]>([]);

  const handleImageUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files || []);
    setUploadedImages(prev => [...prev, ...files]);
    
    // Simulate road condition analysis
    files.forEach((file, index) => {
      const conditions = ['Good', 'Satisfactory', 'Poor', 'Very Poor'];
      const randomCondition = conditions[Math.floor(Math.random() * conditions.length)];
      addRoadCondition(randomCondition);
    });
    
    toast({
      title: "Images Analyzed",
      description: `${files.length} road condition(s) detected`,
    });
  };

  const handleGenerateRoute = async () => {
    if (!startCoords || !endCoords) {
      toast({
        title: "Missing Locations",
        description: "Please select both start and destination points first.",
        variant: "destructive",
      });
      return;
    }
    
    await generateRoute();
    toast({
      title: "Route Generated",
      description: "Your route following real roads has been calculated!",
    });
  };

  return (
    <aside className={`
      fixed left-0 top-16 h-[calc(100vh-4rem)] w-80 bg-background border-r border-border
      transform transition-transform duration-300 z-40 overflow-y-auto
      ${isOpen ? 'translate-x-0' : '-translate-x-full'}
      lg:translate-x-0
    `}>
      <div className="p-4 space-y-6">
        {/* Route Planning Section */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <MapPin className="h-5 w-5" />
              Route Planning
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-2">
              <Button
                variant={isSelecting === 'start' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setSelecting('start')}
                className="flex items-center gap-2"
                disabled={isLoading}
              >
                <Plus className="h-4 w-4" />
                Start
              </Button>
              <Button
                variant={isSelecting === 'end' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setSelecting('end')}
                className="flex items-center gap-2"
                disabled={isLoading}
              >
                <Plus className="h-4 w-4" />
                End
              </Button>
            </div>

            {startCoords && (
              <div className="p-2 bg-green-50 dark:bg-green-950 rounded-lg">
                <p className="text-xs font-medium text-green-700 dark:text-green-300">Start Location</p>
                <p className="text-xs text-green-600 dark:text-green-400">
                  {startCoords[0].toFixed(5)}, {startCoords[1].toFixed(5)}
                </p>
              </div>
            )}

            {endCoords && (
              <div className="p-2 bg-red-50 dark:bg-red-950 rounded-lg">
                <p className="text-xs font-medium text-red-700 dark:text-red-300">Destination</p>
                <p className="text-xs text-red-600 dark:text-red-400">
                  {endCoords[0].toFixed(5)}, {endCoords[1].toFixed(5)}
                </p>
              </div>
            )}

            <div className="flex gap-2">
              <Button 
                onClick={handleGenerateRoute} 
                className="flex-1"
                disabled={isLoading}
              >
                {isLoading ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Generating...
                  </>
                ) : (
                  <>
                    <Route className="h-4 w-4 mr-2" />
                    Generate Route
                  </>
                )}
              </Button>
              <Button variant="outline" onClick={resetRoute} disabled={isLoading}>
                <X className="h-4 w-4" />
              </Button>
            </div>

            {isLoading && (
              <div className="text-center text-sm text-muted-foreground">
                Calculating route following real roads...
              </div>
            )}
          </CardContent>
        </Card>

        {/* Road Condition Analysis */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Image className="h-5 w-5" />
              Road Analysis
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="border-2 border-dashed border-border rounded-lg p-4 text-center">
              <input
                type="file"
                multiple
                accept="image/*"
                onChange={handleImageUpload}
                className="hidden"
                id="image-upload"
                disabled={isLoading}
              />
              <label htmlFor="image-upload" className="cursor-pointer">
                <Upload className="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
                <p className="text-sm text-muted-foreground">
                  Upload road images for AI analysis
                </p>
              </label>
            </div>

            {uploadedImages.length > 0 && (
              <div>
                <p className="text-sm font-medium mb-2">
                  Uploaded: {uploadedImages.length} image(s)
                </p>
                <div className="flex flex-wrap gap-1">
                  {roadConditions.map((condition, index) => (
                    <Badge
                      key={index}
                      variant={
                        condition === 'Good' ? 'default' :
                        condition === 'Satisfactory' ? 'secondary' :
                        'destructive'
                      }
                    >
                      {condition}
                    </Badge>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Route Information */}
        {routeData && (
          <Card>
            <CardHeader>
              <CardTitle>Route Summary</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <p className="text-muted-foreground">Distance</p>
                  <p className="font-medium">{routeData.distance} km</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Duration</p>
                  <p className="font-medium">{routeData.duration}</p>
                </div>
              </div>

              <div>
                <p className="text-sm font-medium mb-2">Road Quality Score</p>
                <div className="space-y-2">
                  <Progress value={routeData.qualityScore} className="h-2" />
                  <p className="text-xs text-muted-foreground">
                    {routeData.qualityScore}/100 - {routeData.qualityScore > 80 ? 'Excellent' : 
                     routeData.qualityScore > 60 ? 'Good' : 
                     routeData.qualityScore > 40 ? 'Fair' : 'Poor'}
                  </p>
                </div>
              </div>

              <div>
                <p className="text-sm font-medium mb-2">Condition Breakdown</p>
                <div className="space-y-1">
                  <div className="flex justify-between text-xs">
                    <span>Good</span>
                    <span>{routeData.conditions.good}%</span>
                  </div>
                  <Progress value={routeData.conditions.good} className="h-1" />
                  
                  <div className="flex justify-between text-xs">
                    <span>Moderate</span>
                    <span>{routeData.conditions.moderate}%</span>
                  </div>
                  <Progress value={routeData.conditions.moderate} className="h-1" />
                  
                  <div className="flex justify-between text-xs">
                    <span>Poor</span>
                    <span>{routeData.conditions.poor}%</span>
                  </div>
                  <Progress value={routeData.conditions.poor} className="h-1" />
                </div>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </aside>
  );
};
