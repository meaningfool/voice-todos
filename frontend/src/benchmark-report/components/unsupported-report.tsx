import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

type UnsupportedReportProps = {
  reportPath: string;
  issues: string[];
};

export function UnsupportedReport({
  reportPath,
  issues,
}: UnsupportedReportProps) {
  return (
    <Alert variant="destructive" className="shadow-sm">
      <AlertTitle>Unsupported report format</AlertTitle>
      <AlertDescription>
        <p>Report path: {reportPath}</p>
        {issues.length > 0 ? (
          <>
            <p className="mt-3">Missing or invalid fields:</p>
            <ul>
              {issues.map((issue) => (
                <li key={issue}>{issue}</li>
              ))}
            </ul>
          </>
        ) : null}
      </AlertDescription>
    </Alert>
  );
}
