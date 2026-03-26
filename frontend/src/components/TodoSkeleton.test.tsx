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
});
