export function TodoSkeleton() {
  return (
    <div className="voice-todo-feed">
      {[1, 2, 3].map((i) => (
        <div
          key={i}
          className="spring-entry voice-todo-card voice-todo-card--skeleton animate-pulse"
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
