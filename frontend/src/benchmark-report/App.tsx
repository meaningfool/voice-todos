import { useState } from "react";

import { Card, CardContent } from "@/components/ui/card";
import { BenchmarkHeader } from "./components/benchmark-header";
import { EntryComparisonTable } from "./components/entry-comparison-table";
import { EntryDetail } from "./components/entry-detail";
import { UnsupportedReport } from "./components/unsupported-report";
import type { BenchmarkEntry, BenchmarkReportBootstrap } from "./types";
import { validateBootstrap } from "./types";

type BenchmarkReportAppProps = {
  bootstrap: unknown;
};

export function BenchmarkReportApp({ bootstrap }: BenchmarkReportAppProps) {
  const validated = validateBootstrap(bootstrap);
  if (!validated.ok) {
    return (
      <main className="benchmark-report-shell">
        <UnsupportedReport
          reportPath={validated.reportPath}
          issues={validated.issues}
        />
      </main>
    );
  }

  return <BenchmarkReportView bootstrap={validated.value} />;
}

function BenchmarkReportView({
  bootstrap,
}: {
  bootstrap: BenchmarkReportBootstrap;
}) {
  const [selectedEntryId, setSelectedEntryId] = useState<string | null>(
    bootstrap.report.entries[0]?.entry_id ?? null,
  );

  const selectedEntry =
    bootstrap.report.entries.find((entry) => entry.entry_id === selectedEntryId) ??
    null;

  return (
    <main className="benchmark-report-shell">
      <div className="benchmark-report-layout">
        <BenchmarkHeader report={bootstrap.report} />

        <Card className="overflow-hidden">
          <CardContent className="p-0">
            <EntryComparisonTable
              entries={bootstrap.report.entries}
              selectedEntryId={selectedEntryId}
              onSelectEntry={setSelectedEntryId}
            />
          </CardContent>
        </Card>

        <EntryDetail entry={selectedEntry as BenchmarkEntry | null} />
      </div>
    </main>
  );
}
