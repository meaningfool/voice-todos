import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { Todo } from "../types";

const priorityCircle: Record<string, string> = {
  high: "border-red-500",
  medium: "border-orange-400",
  low: "border-blue-500",
};

interface Props {
  todo: Todo;
}

export function TodoCard({ todo }: Props) {
  const circleColor = todo.priority
    ? priorityCircle[todo.priority]
    : "border-gray-300";

  return (
    <Card className="hover:shadow-sm transition-shadow">
      <CardContent className="flex items-start gap-3 p-4">
        <div
          className={`w-5 h-5 rounded-full border-2 shrink-0 mt-0.5 ${circleColor}`}
        />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium leading-snug">{todo.text}</p>
          <div className="flex flex-wrap gap-1.5 mt-1.5">
            {todo.dueDate && (
              <Badge variant="secondary" className="text-red-600 bg-red-50 text-xs">
                📅 {todo.dueDate}
              </Badge>
            )}
            {todo.priority && (
              <Badge variant="secondary" className="text-orange-600 bg-orange-50 text-xs">
                ⚡ {todo.priority}
              </Badge>
            )}
            {todo.category && (
              <Badge variant="secondary" className="text-blue-600 bg-blue-50 text-xs">
                📁 {todo.category}
              </Badge>
            )}
            {todo.assignTo && (
              <Badge variant="secondary" className="text-purple-600 bg-purple-50 text-xs">
                👤 {todo.assignTo}
              </Badge>
            )}
            {todo.notification && (
              <Badge variant="secondary" className="text-green-600 bg-green-50 text-xs">
                🔔 {todo.notification}
              </Badge>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
