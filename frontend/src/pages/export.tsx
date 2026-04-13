import { useState, useMemo } from "react";
import { useMutation } from "@tanstack/react-query";
import { useLeads } from "@/hooks/use-leads";
import { api } from "@/lib/api";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";
import { DownloadIcon, Loader2Icon, FileSpreadsheetIcon } from "lucide-react";
import type { PipelineStage } from "@/lib/types";

const ALL_STAGES: { value: PipelineStage; label: string }[] = [
  { value: "NEW", label: "New" },
  { value: "APPROVED", label: "Approved" },
  { value: "CONTACTED", label: "Contacted" },
  { value: "MEETING", label: "Meeting" },
  { value: "PROPOSAL", label: "Proposal" },
  { value: "CLOSED", label: "Closed" },
  { value: "DISAPPROVED", label: "Disapproved" },
];

export default function ExportPage() {
  const [selectedStages, setSelectedStages] = useState<PipelineStage[]>([
    "NEW",
    "APPROVED",
    "CONTACTED",
    "MEETING",
    "PROPOSAL",
    "CLOSED",
  ]);

  const { data: leadsData, isLoading: leadsLoading } = useLeads({
    page_size: 500,
  });

  const matchingCount = useMemo(() => {
    if (!leadsData?.items) return 0;
    return leadsData.items.filter((lead) =>
      selectedStages.includes(lead.pipeline_stage)
    ).length;
  }, [leadsData, selectedStages]);

  const exportMutation = useMutation({
    mutationFn: () =>
      api.export.xlsx(
        selectedStages.length < 5 ? selectedStages : undefined
      ),
    onSuccess: (blob) => {
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `leads-export-${new Date().toISOString().slice(0, 10)}.xlsx`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      toast.success("Export downloaded");
    },
    onError: (error) => {
      toast.error(
        `Export failed: ${error instanceof Error ? error.message : "Unknown error"}`
      );
    },
  });

  const toggleStage = (stage: PipelineStage) => {
    setSelectedStages((prev) =>
      prev.includes(stage)
        ? prev.filter((s) => s !== stage)
        : [...prev, stage]
    );
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">
          Export
        </h1>
        <p className="text-sm text-muted-foreground">
          Download your leads as an Excel spreadsheet.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Filters</CardTitle>
            <CardDescription>
              Choose which leads to include in the export.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-3">
              <Label>Pipeline Stages</Label>
              <div className="flex flex-wrap gap-2">
                {ALL_STAGES.map(({ value, label }) => {
                  const isSelected = selectedStages.includes(value);
                  return (
                    <Button
                      key={value}
                      variant={isSelected ? "default" : "outline"}
                      size="sm"
                      onClick={() => toggleStage(value)}
                    >
                      {label}
                    </Button>
                  );
                })}
              </div>
              <div className="flex gap-2">
                <Button
                  variant="ghost"
                  size="xs"
                  onClick={() =>
                    setSelectedStages(ALL_STAGES.map((s) => s.value))
                  }
                >
                  Select All
                </Button>
                <Button
                  variant="ghost"
                  size="xs"
                  onClick={() => setSelectedStages([])}
                >
                  Clear
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Summary</CardTitle>
            <CardDescription>
              Preview before downloading.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="flex flex-col items-center justify-center gap-4 rounded-lg border border-dashed border-border p-8">
              <FileSpreadsheetIcon className="size-12 text-muted-foreground" />
              {leadsLoading ? (
                <Skeleton className="h-8 w-32" />
              ) : (
                <div className="text-center">
                  <p className="text-3xl font-bold">{matchingCount}</p>
                  <p className="text-sm text-muted-foreground">
                    leads matching filters
                  </p>
                </div>
              )}
            </div>

            <div className="space-y-2 text-sm text-muted-foreground">
              <div className="flex justify-between">
                <span>Stages:</span>
                <span>
                  {selectedStages.length === ALL_STAGES.length
                    ? "All"
                    : selectedStages.join(", ") || "None"}
                </span>
              </div>
            </div>

            <Button
              onClick={() => exportMutation.mutate()}
              disabled={
                exportMutation.isPending ||
                selectedStages.length === 0 ||
                matchingCount === 0
              }
              className="w-full"
            >
              {exportMutation.isPending ? (
                <>
                  <Loader2Icon className="size-4 animate-spin" />
                  Exporting...
                </>
              ) : (
                <>
                  <DownloadIcon className="size-4" />
                  Download Excel
                </>
              )}
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
