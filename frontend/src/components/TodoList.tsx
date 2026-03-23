import type { Todo } from "../types";
import { TodoCard } from "./TodoCard";

interface Props {
  todos: Todo[];
}

export function TodoList({ todos }: Props) {
  if (todos.length === 0) return null;

  return (
    <div className="flex flex-col gap-3 mt-4">
      <p className="text-xs uppercase tracking-wide text-gray-500 font-semibold">
        Extracted Todos ({todos.length})
      </p>
      {todos.map((todo, index) => (
        <TodoCard key={index} todo={todo} />
      ))}
    </div>
  );
}
