import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { FileText } from "lucide-react";

interface BuildingSummarySectionProps {
  summary: string;
}

export function BuildingSummarySection({
  summary,
}: BuildingSummarySectionProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <FileText className="size-4 text-muted-foreground" />
          Building Summary
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="leading-relaxed text-foreground">{summary}</p>
      </CardContent>
    </Card>
  );
}
