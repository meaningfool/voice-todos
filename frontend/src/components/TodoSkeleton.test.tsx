import { render } from "@testing-library/react";
import { TodoSkeleton } from "./TodoSkeleton";

describe("TodoSkeleton", () => {
  it("renders 3 skeleton cards by default", () => {
    const { getAllByTestId } = render(<TodoSkeleton />);
    const cards = getAllByTestId("todo-skeleton-card");
    expect(cards).toHaveLength(3);
  });

  it("renders 2 skeleton cards when count is 2", () => {
    const { getAllByTestId } = render(<TodoSkeleton count={2} />);
    const cards = getAllByTestId("todo-skeleton-card");
    expect(cards).toHaveLength(2);
  });

  it("applies the compact wrapper class when compact is true", () => {
    const { container } = render(<TodoSkeleton count={1} compact />);
    const feed = container.firstElementChild;

    expect(feed).toHaveClass("voice-todo-feed");
    expect(feed).toHaveClass("voice-todo-feed--compact");
  });
});
