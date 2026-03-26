interface Props {
  count?: number;
  compact?: boolean;
}

export function TodoSkeleton({ count = 3, compact = false }: Props) {
  return (
    <div className={compact ? "voice-todo-feed voice-todo-feed--compact" : "voice-todo-feed"}>
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className="spring-entry voice-todo-card voice-todo-card--skeleton animate-pulse"
          data-testid="todo-skeleton-card"
        >
          <div className="voice-todo-card__body">
            <div className="voice-todo-circle voice-todo-circle--skeleton" />
            <div className="voice-todo-content">
              <div className="voice-todo-skeleton-line voice-todo-skeleton-line--title" />
              <div className="voice-meta-row">
                <div className="voice-todo-skeleton-chip voice-todo-skeleton-chip--wide" />
                <div className="voice-todo-skeleton-chip" />
                <div className="voice-todo-skeleton-chip voice-todo-skeleton-chip--wide" />
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
