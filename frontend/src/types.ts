export interface Todo {
  text: string;
  priority?: "high" | "medium" | "low";
  category?: string;
  dueDate?: string;
  notification?: string;
  assignTo?: string;
}
