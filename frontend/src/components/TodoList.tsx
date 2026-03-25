import { useEffect, useRef, useState } from "react";
import type { Todo } from "../types";
import { TodoCard } from "./TodoCard";
import { getChangedTodoIndices } from "../lib/todoDiff";

interface Props {
  todos: Todo[];
}

export function TodoList({ todos }: Props) {
  const previousTodosRef = useRef<Todo[]>([]);
  const highlightTimeoutRef = useRef<number | null>(null);
  const [highlightedIndices, setHighlightedIndices] = useState<number[]>([]);

  useEffect(() => {
    return () => {
      if (highlightTimeoutRef.current !== null) {
        window.clearTimeout(highlightTimeoutRef.current);
      }
    };
  }, []);

  useEffect(() => {
    const changedIndices = getChangedTodoIndices(previousTodosRef.current, todos);
    previousTodosRef.current = todos.map((todo) => ({ ...todo }));

    if (todos.length === 0) {
      if (highlightTimeoutRef.current !== null) {
        window.clearTimeout(highlightTimeoutRef.current);
        highlightTimeoutRef.current = null;
      }
      setHighlightedIndices([]);
      return;
    }

    if (changedIndices.length === 0) {
      return;
    }

    if (highlightTimeoutRef.current !== null) {
      window.clearTimeout(highlightTimeoutRef.current);
    }

    setHighlightedIndices(changedIndices);
    highlightTimeoutRef.current = window.setTimeout(() => {
      setHighlightedIndices([]);
      highlightTimeoutRef.current = null;
    }, 1000);
  }, [todos]);

  if (todos.length === 0) return null;

  return (
    <div className="voice-todo-feed">
      {todos.map((todo, index) => (
        <TodoCard
          key={`${todo.text}-${index}`}
          todo={todo}
          index={index}
          highlighted={highlightedIndices.includes(index)}
        />
      ))}
    </div>
  );
}
