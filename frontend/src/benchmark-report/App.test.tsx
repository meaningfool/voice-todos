import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BenchmarkReportApp } from "./App";
import type { BenchmarkReportBootstrap } from "./types";

const validBootstrap: BenchmarkReportBootstrap = {
  reportPath: "/tmp/todo_extraction_bench_v1.json",
  report: {
    benchmark_id: "todo_extraction_bench_v1",
    hosted_dataset: "dataset-1",
    focus: "model",
    display_headline_metric: "passed / total",
    headline_metric: "todo_count_match",
    stale: false,
    entries: [
      {
        entry_id: "gemini3_flash_default",
        label: "Gemini 3 Flash / default",
        status: "current",
        selected_run_id: "run-1",
        selected_timestamp: "2026-04-16T12:00:00Z",
        headline_metric_value: 24 / 26,
        total_case_count: 26,
        passed_case_count: 24,
        incorrect_case_count: 2,
        incomplete_case_count: 0,
        completed_case_count: 26,
        failure_count: 0,
        average_case_duration_s: 1.2,
        max_case_duration_s: 2.5,
        incorrect_cases: [
          {
            case_id: "question-not-commitment",
            inputs: {
              transcript:
                "I was wondering, should I call David tomorrow, or is that unnecessary?",
            },
            expected_output: [],
            actual_output: [
              {
                text: "Call David",
                priority: null,
                category: "Communication",
                due_date: "2026-03-25",
                notification: null,
                assign_to: null,
              },
            ],
          },
        ],
        incomplete_cases: [],
        failures: [],
        slowest_cases: [
          { case_id: "dense-run-on-four", duration_s: 2.5 },
        ],
      },
      {
        entry_id: "mistral_small_4_default",
        label: "Mistral Small 4 / default",
        status: "current",
        selected_run_id: "run-2",
        selected_timestamp: "2026-04-16T12:10:00Z",
        headline_metric_value: 24 / 26,
        total_case_count: 26,
        passed_case_count: 24,
        incorrect_case_count: 1,
        incomplete_case_count: 1,
        completed_case_count: 25,
        failure_count: 1,
        average_case_duration_s: 2.1,
        max_case_duration_s: 4.3,
        incorrect_cases: [
          {
            case_id: "mild-misrecognition-two",
            inputs: {
              transcript: "By oat milk tonight. Zen email Sarah the revised budget.",
            },
            expected_output: [
              {
                text: "Buy oat milk tonight",
                priority: null,
                category: null,
                due_date: null,
                notification: null,
                assign_to: null,
              },
              {
                text: "Email Sarah the revised budget",
                priority: null,
                category: null,
                due_date: null,
                notification: null,
                assign_to: null,
              },
            ],
            actual_output: [
              {
                text: "Buy oat milk tonight",
                priority: null,
                category: null,
                due_date: null,
                notification: null,
                assign_to: null,
              },
            ],
          },
        ],
        incomplete_cases: [
          {
            case_id: "merge-and-keep-separate",
            inputs: {
              transcript:
                "Buy milk, buy bread, call Marc, and actually make the milk and bread one grocery run, but keep calling Marc separate.",
            },
            expected_output: [
              {
                text: "Do one grocery run for milk and bread",
                priority: null,
                category: null,
                due_date: null,
                notification: null,
                assign_to: null,
              },
              {
                text: "Call Marc",
                priority: null,
                category: null,
                due_date: null,
                notification: null,
                assign_to: null,
              },
            ],
            summary: "Exceeded maximum retries (1) for output validation",
            exception_type: "pydantic_ai.exceptions.UnexpectedModelBehavior",
            validator_feedback:
              "Please return text or include your response in a tool call.",
            actual_output: null,
          },
        ],
        failures: [
          {
            case_id: "merge-and-keep-separate",
            category: "case_failure",
            summary: "Exceeded maximum retries (1) for output validation",
          },
        ],
        slowest_cases: [
          { case_id: "long-noisy-three-with-past", duration_s: 4.3 },
        ],
      },
    ],
  },
};

describe("BenchmarkReportApp", () => {
  it("renders benchmark summary and comparison table", () => {
    render(<BenchmarkReportApp bootstrap={validBootstrap} />);

    expect(screen.getByText("todo_extraction_bench_v1")).toBeInTheDocument();
    const table = screen.getByRole("table", { name: "Benchmark entries" });
    expect(table).toBeInTheDocument();
    expect(within(table).getByRole("columnheader", { name: "Passed" })).toBeInTheDocument();
    expect(within(table).getByRole("columnheader", { name: "Incorrect" })).toBeInTheDocument();
    expect(within(table).getByRole("columnheader", { name: "Incomplete" })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Gemini 3 Flash / default" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Mistral Small 4 / default" }),
    ).toBeInTheDocument();
  });

  it("shows same-page selected entry detail and updates it on row click", async () => {
    const user = userEvent.setup();
    render(<BenchmarkReportApp bootstrap={validBootstrap} />);

    const selectedRunCard = screen.getByText("Selected run").closest("[data-slot='card']");
    expect(selectedRunCard).not.toBeNull();

    expect(screen.getByText("run-1")).toBeInTheDocument();
    expect(within(selectedRunCard as HTMLElement).getByText("24 / 26")).toBeInTheDocument();
    expect(screen.getByText("Incorrect cases")).toBeInTheDocument();
    expect(screen.getByText("question-not-commitment")).toBeInTheDocument();
    expect(screen.getByText("dense-run-on-four")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Mistral Small 4 \/ default/i }));

    expect(screen.getByText("run-2")).toBeInTheDocument();
    expect(screen.getByText("Incomplete cases")).toBeInTheDocument();
    expect(screen.getByText("mild-misrecognition-two")).toBeInTheDocument();
    expect(screen.getByText("merge-and-keep-separate")).toBeInTheDocument();
    expect(
      screen.getByText("Exceeded maximum retries (1) for output validation"),
    ).toBeInTheDocument();
    expect(screen.getByText("long-noisy-three-with-past")).toBeInTheDocument();
  });

  it("renders a clear unsupported report failure state", () => {
    render(
      <BenchmarkReportApp
        bootstrap={{
          reportPath: "/tmp/bad.json",
          report: {
            benchmark_id: "todo_extraction_bench_v1",
          } as never,
        }}
      />,
    );

    const alert = screen.getByRole("alert");
    expect(screen.getByText("Unsupported report format")).toBeInTheDocument();
    expect(alert).toHaveTextContent("/tmp/bad.json");
  });
});
