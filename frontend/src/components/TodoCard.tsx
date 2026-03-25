import { AppIcon } from "./AppIcon";
import { cn } from "../lib/utils";
import type { Todo } from "../types";

const priorityCircle: Record<string, string> = {
  high: "voice-todo-circle--high",
  medium: "voice-todo-circle--medium",
  low: "voice-todo-circle--low",
};

type ChipIcon = "calendar" | "tag" | "user";

interface Props {
  todo: Todo;
  highlighted?: boolean;
  index?: number;
}

function MetaChip({
  children,
  icon,
  className,
}: {
  children: string;
  icon?: ChipIcon;
  className?: string;
}) {
  return (
    <span className={cn("voice-meta-chip", className)}>
      {icon ? <AppIcon name={icon} className="voice-meta-chip-icon" /> : null}
      <span>{children}</span>
    </span>
  );
}

export function TodoCard({ todo, highlighted = false, index = 0 }: Props) {
  const circleClass = todo.priority ? priorityCircle[todo.priority] : undefined;

  return (
    <article
      data-testid={`todo-card-${index}`}
      data-highlighted={highlighted ? "true" : "false"}
      className={cn("spring-entry voice-todo-card", highlighted && "flash-orange")}
    >
      <div className="voice-todo-card__body">
        <div className={cn("voice-todo-circle", circleClass)} />
        <div className="voice-todo-content">
          <p className="voice-todo-title">{todo.text}</p>
          <div className="voice-meta-row">
            {todo.dueDate ? (
              <MetaChip icon="calendar" className="voice-meta-chip--calendar">
                {todo.dueDate}
              </MetaChip>
            ) : null}
            {todo.priority ? (
              <MetaChip
                className={cn(
                  "voice-meta-chip--priority",
                  `voice-meta-chip--priority-${todo.priority}`,
                )}
              >
                {todo.priority}
              </MetaChip>
            ) : null}
            {todo.category ? (
              <MetaChip icon="tag" className="voice-meta-chip--tag">
                {todo.category}
              </MetaChip>
            ) : null}
            {todo.assignTo ? (
              <MetaChip icon="user" className="voice-meta-chip--user">
                {todo.assignTo}
              </MetaChip>
            ) : null}
            {todo.notification ? (
              <MetaChip className="voice-meta-chip--notification">
                {todo.notification}
              </MetaChip>
            ) : null}
          </div>
        </div>
      </div>
    </article>
  );
}
