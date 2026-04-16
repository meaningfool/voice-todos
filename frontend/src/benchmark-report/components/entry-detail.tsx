import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import type {
  BenchmarkEntry,
  BenchmarkIncompleteCase,
  BenchmarkIncorrectCase,
} from "../types";

type EntryDetailProps = {
  entry: BenchmarkEntry | null;
};

export function EntryDetail({ entry }: EntryDetailProps) {
  if (!entry) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>No entry selected</CardTitle>
          <CardDescription>
            Pick a benchmark entry from the comparison table to inspect its
            selected run.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <div className="grid gap-4">
      <Card>
        <CardHeader>
          <CardDescription>Selected run</CardDescription>
          <CardTitle>{entry.label}</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2">
          <DetailMetric label="Run ID" value={entry.selected_run_id ?? "—"} />
          <DetailMetric
            label="Selected timestamp"
            value={entry.selected_timestamp ?? "—"}
          />
          <DetailMetric
            label="Headline metric"
            value={`${entry.passed_case_count} / ${entry.total_case_count}`}
          />
          <DetailMetric label="Passed" value={String(entry.passed_case_count)} />
          <DetailMetric
            label="Incorrect"
            value={String(entry.incorrect_case_count)}
          />
          <DetailMetric
            label="Incomplete"
            value={String(entry.incomplete_case_count)}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Incorrect cases</CardTitle>
          <CardDescription>
            {entry.incorrect_cases?.length
              ? `${entry.incorrect_cases.length} completed case${entry.incorrect_cases.length === 1 ? "" : "s"} missed the benchmark assertion.`
              : "Completed cases that returned valid output but missed the benchmark assertion."}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {entry.incorrect_cases?.length ? (
            <div className="grid gap-4">
              {entry.incorrect_cases.map((incorrectCase) => (
                <IncorrectCaseCard
                  key={incorrectCase.case_id}
                  incorrectCase={incorrectCase}
                />
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              No incorrect completed cases recorded for this entry.
            </p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Incomplete cases</CardTitle>
          <CardDescription>
            {entry.incomplete_cases?.length
              ? `${entry.incomplete_cases.length} case${entry.incomplete_cases.length === 1 ? "" : "s"} did not complete cleanly.`
              : "Cases that did not complete cleanly because of runtime, validation, or provider errors."}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {entry.incomplete_cases?.length ? (
            <div className="grid gap-4">
              {entry.incomplete_cases.map((incompleteCase) => (
                <IncompleteCaseCard
                  key={incompleteCase.case_id}
                  incompleteCase={incompleteCase}
                />
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              No incomplete cases recorded for this entry.
            </p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Slowest cases</CardTitle>
          <CardDescription>
            The slowest completed cases captured for this entry.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {entry.slowest_cases?.length ? (
            <ul className="grid gap-3">
              {entry.slowest_cases.map((slowCase) => (
                <li key={`${slowCase.case_id}-${slowCase.duration_s}`} className="flex items-center justify-between gap-4">
                  <span className="font-medium text-foreground">{slowCase.case_id}</span>
                  <span className="text-sm text-muted-foreground">
                    {slowCase.duration_s.toFixed(2)}s
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">
              No completed-case timings recorded for this entry.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function IncorrectCaseCard({
  incorrectCase,
}: {
  incorrectCase: BenchmarkIncorrectCase;
}) {
  return (
    <div className="grid gap-3 rounded-xl border border-border/70 p-4">
      <p className="font-semibold text-foreground">{incorrectCase.case_id}</p>
      <CasePayload label="Input" value={incorrectCase.inputs} />
      <CasePayload label="Expected output" value={incorrectCase.expected_output} />
      <CasePayload label="Actual output" value={incorrectCase.actual_output} />
    </div>
  );
}

function IncompleteCaseCard({
  incompleteCase,
}: {
  incompleteCase: BenchmarkIncompleteCase;
}) {
  return (
    <div className="grid gap-3 rounded-xl border border-border/70 p-4">
      <p className="font-semibold text-foreground">{incompleteCase.case_id}</p>
      <DetailMetric label="Failure reason" value={incompleteCase.summary} />
      <CasePayload label="Input" value={incompleteCase.inputs} />
      <CasePayload
        label="Expected output"
        value={incompleteCase.expected_output}
      />
      {incompleteCase.validator_feedback ? (
        <CasePayload
          label="Validator feedback"
          value={incompleteCase.validator_feedback}
        />
      ) : null}
      <CasePayload
        label="Actual output"
        value={incompleteCase.actual_output ?? "No valid structured output emitted."}
      />
    </div>
  );
}

function CasePayload({ label, value }: { label: string; value: unknown }) {
  return (
    <div className="grid gap-1">
      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">
        {label}
      </p>
      <pre className="overflow-x-auto rounded-lg bg-muted/60 p-3 text-xs leading-5 whitespace-pre-wrap text-foreground">
        {formatPayload(value)}
      </pre>
    </div>
  );
}

function formatPayload(value: unknown) {
  if (typeof value === "string") {
    return value;
  }
  return JSON.stringify(value, null, 2);
}

function DetailMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="space-y-1">
      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">
        {label}
      </p>
      <p className="text-sm font-medium text-foreground">{value}</p>
    </div>
  );
}
