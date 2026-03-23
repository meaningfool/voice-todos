import { Card, CardContent } from "@/components/ui/card";

export function TodoSkeleton() {
  return (
    <div className="flex flex-col gap-3 mt-4">
      {[1, 2, 3].map((i) => (
        <Card key={i} className="animate-pulse">
          <CardContent className="flex items-start gap-3 p-4">
            <div className="w-5 h-5 rounded-full bg-gray-200 shrink-0" />
            <div className="flex-1 space-y-2">
              <div className="h-4 bg-gray-200 rounded w-3/4" />
              <div className="h-3 bg-gray-100 rounded w-1/3" />
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
