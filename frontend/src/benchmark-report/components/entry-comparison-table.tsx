import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";
import type { BenchmarkEntry } from "../types";

type EntryComparisonTableProps = {
  entries: BenchmarkEntry[];
  selectedEntryId: string | null;
  onSelectEntry: (entryId: string) => void;
};

export function EntryComparisonTable({
  entries,
  selectedEntryId,
  onSelectEntry,
}: EntryComparisonTableProps) {
  return (
    <Table aria-label="Benchmark entries">
      <TableHeader>
        <TableRow>
          <TableHead>Label</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Headline</TableHead>
          <TableHead>Passed</TableHead>
          <TableHead>Incorrect</TableHead>
          <TableHead>Incomplete</TableHead>
          <TableHead>Avg duration</TableHead>
          <TableHead>Max duration</TableHead>
          <TableHead>Selected timestamp</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {entries.map((entry) => {
          const selected = entry.entry_id === selectedEntryId;
          return (
            <TableRow key={entry.entry_id} data-state={selected ? "selected" : undefined}>
              <TableCell className="font-medium">
                <button
                  type="button"
                  className={cn(
                    "text-left font-semibold text-foreground underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                    selected && "text-primary",
                  )}
                  onClick={() => onSelectEntry(entry.entry_id)}
                >
                  {entry.label}
                </button>
              </TableCell>
              <TableCell>
                <Badge variant={entry.status === "current" ? "secondary" : "outline"}>
                  {entry.status}
                </Badge>
              </TableCell>
              <TableCell>{formatHeadline(entry)}</TableCell>
              <TableCell>{entry.passed_case_count}</TableCell>
              <TableCell>{entry.incorrect_case_count}</TableCell>
              <TableCell>{entry.incomplete_case_count}</TableCell>
              <TableCell>{formatDuration(entry.average_case_duration_s)}</TableCell>
              <TableCell>{formatDuration(entry.max_case_duration_s)}</TableCell>
              <TableCell>{entry.selected_timestamp ?? "—"}</TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}

function formatHeadline(entry: BenchmarkEntry) {
  if (entry.total_case_count <= 0) {
    return "—";
  }
  return `${entry.passed_case_count} / ${entry.total_case_count}`;
}

function formatDuration(value: number | null | undefined) {
  return typeof value === "number" ? `${value.toFixed(2)}s` : "—";
}
