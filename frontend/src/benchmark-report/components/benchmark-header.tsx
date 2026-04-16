import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import type { BenchmarkReport } from "../types";

type BenchmarkHeaderProps = {
  report: BenchmarkReport;
};

export function BenchmarkHeader({ report }: BenchmarkHeaderProps) {
  return (
    <Card>
      <CardHeader className="gap-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="space-y-1">
            <CardDescription>Benchmark report</CardDescription>
            <CardTitle className="text-2xl tracking-tight">
              {report.benchmark_id}
            </CardTitle>
          </div>
          <Badge variant={report.stale ? "destructive" : "secondary"}>
            {report.stale ? "Stale" : "Current"}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="grid gap-4 sm:grid-cols-3">
        <HeaderMetric
          label="Displayed headline"
          value={report.display_headline_metric}
        />
        <HeaderMetric label="Hosted dataset" value={report.hosted_dataset} />
        <HeaderMetric label="Focus" value={report.focus} />
      </CardContent>
    </Card>
  );
}

function HeaderMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="space-y-1">
      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">
        {label}
      </p>
      <p className="text-sm font-medium text-foreground">{value}</p>
    </div>
  );
}
