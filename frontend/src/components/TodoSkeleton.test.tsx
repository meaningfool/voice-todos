import { render } from "@testing-library/react";
import { TodoSkeleton } from "./TodoSkeleton";

describe("TodoSkeleton", () => {
  it("renders 3 skeleton placeholder cards", () => {
    const { container } = render(<TodoSkeleton />);
    const cards = container.querySelectorAll("[class*='animate-pulse']");
    expect(cards).toHaveLength(3);
  });
});
