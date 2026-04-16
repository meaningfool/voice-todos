export type BenchmarkCaseFailure = {
  case_id: string;
  category?: string;
  summary?: string;
};

export type BenchmarkIncorrectCase = {
  case_id: string;
  inputs: Record<string, unknown>;
  expected_output: unknown[];
  actual_output: unknown;
};

export type BenchmarkIncompleteCase = {
  case_id: string;
  inputs: Record<string, unknown>;
  expected_output: unknown[];
  summary: string;
  exception_type?: string | null;
  validator_feedback?: string | null;
  actual_output?: unknown | null;
};

export type BenchmarkSlowCase = {
  case_id: string;
  duration_s: number;
};

export type BenchmarkEntry = {
  entry_id: string;
  label: string;
  status: string;
  selected_run_id?: string | null;
  selected_timestamp?: string | null;
  headline_metric_value?: number | null;
  total_case_count: number;
  passed_case_count: number;
  incorrect_case_count: number;
  incomplete_case_count: number;
  completed_case_count?: number;
  failure_count?: number;
  average_case_duration_s?: number | null;
  max_case_duration_s?: number | null;
  incorrect_cases?: BenchmarkIncorrectCase[];
  incomplete_cases?: BenchmarkIncompleteCase[];
  failures?: BenchmarkCaseFailure[];
  slowest_cases?: BenchmarkSlowCase[];
};

export type BenchmarkReport = {
  benchmark_id: string;
  hosted_dataset: string;
  focus: string;
  headline_metric: string;
  display_headline_metric: string;
  stale: boolean;
  entries: BenchmarkEntry[];
};

export type BenchmarkReportBootstrap = {
  reportPath: string;
  report: BenchmarkReport;
};

export type SupportedBootstrap =
  | { ok: true; value: BenchmarkReportBootstrap }
  | { ok: false; reportPath: string; issues: string[] };

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isEntry(value: unknown): value is BenchmarkEntry {
  if (!isObject(value)) {
    return false;
  }
  return (
    typeof value.entry_id === "string" &&
    typeof value.label === "string" &&
    typeof value.status === "string" &&
    typeof value.total_case_count === "number" &&
    typeof value.passed_case_count === "number" &&
    typeof value.incorrect_case_count === "number" &&
    typeof value.incomplete_case_count === "number"
  );
}

export function validateBootstrap(bootstrap: unknown): SupportedBootstrap {
  const issues: string[] = [];
  if (!isObject(bootstrap)) {
    return {
      ok: false,
      reportPath: "(unknown report path)",
      issues: ["bootstrap payload is not an object"],
    };
  }

  const reportPath =
    typeof bootstrap.reportPath === "string"
      ? bootstrap.reportPath
      : "(unknown report path)";
  if (typeof bootstrap.reportPath !== "string") {
    issues.push("reportPath");
  }

  const report = bootstrap.report;
  if (!isObject(report)) {
    issues.push("report");
  } else {
    if (typeof report.benchmark_id !== "string") {
      issues.push("report.benchmark_id");
    }
    if (typeof report.hosted_dataset !== "string") {
      issues.push("report.hosted_dataset");
    }
    if (typeof report.focus !== "string") {
      issues.push("report.focus");
    }
    if (typeof report.headline_metric !== "string") {
      issues.push("report.headline_metric");
    }
    if (typeof report.display_headline_metric !== "string") {
      issues.push("report.display_headline_metric");
    }
    if (!Array.isArray(report.entries)) {
      issues.push("report.entries");
    } else if (!report.entries.every(isEntry)) {
      issues.push("report.entries[*]");
    }
  }

  if (issues.length > 0) {
    return { ok: false, reportPath, issues };
  }

  return {
    ok: true,
    value: bootstrap as BenchmarkReportBootstrap,
  };
}
