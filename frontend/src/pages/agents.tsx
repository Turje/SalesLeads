import { useAgentStatus, useTriggerAgents } from "@/hooks/use-agents";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { toast } from "sonner";
import {
  Loader2Icon,
  PlayIcon,
  UsersIcon,
  ClockIcon,
  ActivityIcon,
} from "lucide-react";

const STAGE_LABELS: Record<string, string> = {
  NEW: "New",
  CONTACTED: "Contacted",
  MEETING: "Meeting",
  PROPOSAL: "Proposal",
  CLOSED: "Closed",
};

export default function AgentsPage() {
  const { data: status, isLoading } = useAgentStatus();
  const triggerMutation = useTriggerAgents();

  const handleRunPipeline = () => {
    triggerMutation.mutate(undefined, {
      onSuccess: () => {
        toast.success("Pipeline triggered successfully");
      },
      onError: (error) => {
        toast.error(
          `Failed to trigger pipeline: ${error instanceof Error ? error.message : "Unknown error"}`
        );
      },
    });
  };

  const activePipelineLeads = status
    ? Object.entries(status.stage_counts)
        .filter(([stage]) => stage !== "CLOSED")
        .reduce((sum, [, count]) => sum + count, 0)
    : 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">
            Agent Status
          </h1>
          <p className="text-sm text-muted-foreground">
            Monitor your lead generation agents and run the pipeline.
          </p>
        </div>
        <Button
          onClick={handleRunPipeline}
          disabled={triggerMutation.isPending}
        >
          {triggerMutation.isPending ? (
            <>
              <Loader2Icon className="size-4 animate-spin" />
              Running...
            </>
          ) : (
            <>
              <PlayIcon className="size-4" />
              Run Pipeline
            </>
          )}
        </Button>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {isLoading ? (
          <>
            {Array.from({ length: 3 }).map((_, i) => (
              <Card key={i} size="sm">
                <CardHeader>
                  <Skeleton className="h-4 w-24" />
                </CardHeader>
                <CardContent>
                  <Skeleton className="h-8 w-16" />
                </CardContent>
              </Card>
            ))}
          </>
        ) : (
          <>
            <Card size="sm">
              <CardHeader>
                <div className="flex items-center gap-2">
                  <UsersIcon className="size-4 text-muted-foreground" />
                  <CardTitle className="text-sm text-muted-foreground">
                    Total Leads
                  </CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold">
                  {status?.total_leads ?? 0}
                </p>
              </CardContent>
            </Card>

            <Card size="sm">
              <CardHeader>
                <div className="flex items-center gap-2">
                  <ClockIcon className="size-4 text-muted-foreground" />
                  <CardTitle className="text-sm text-muted-foreground">
                    Last Run
                  </CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                <p className="text-sm font-medium">
                  {status?.last_run?.finished_at
                    ? new Date(
                        String(status.last_run.finished_at)
                      ).toLocaleString()
                    : "Never"}
                </p>
                {typeof status?.last_run?.status === "string" && (
                  <Badge
                    variant={
                      status.last_run.status === "completed"
                        ? "default"
                        : "destructive"
                    }
                    className="mt-1"
                  >
                    {status.last_run.status}
                  </Badge>
                )}
              </CardContent>
            </Card>

            <Card size="sm">
              <CardHeader>
                <div className="flex items-center gap-2">
                  <ActivityIcon className="size-4 text-muted-foreground" />
                  <CardTitle className="text-sm text-muted-foreground">
                    Active Pipeline
                  </CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold">{activePipelineLeads}</p>
                <p className="text-xs text-muted-foreground">
                  leads in active stages
                </p>
              </CardContent>
            </Card>
          </>
        )}
      </div>

      <Separator />

      <div>
        <h2 className="text-lg font-semibold text-foreground mb-4">
          Stage Distribution
        </h2>
        {isLoading ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {Array.from({ length: 5 }).map((_, i) => (
              <Card key={i} size="sm">
                <CardContent className="pt-4">
                  <Skeleton className="h-4 w-20 mb-2" />
                  <Skeleton className="h-8 w-12" />
                </CardContent>
              </Card>
            ))}
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {Object.entries(status?.stage_counts ?? {}).map(
              ([stage, count]) => {
                const total = status?.total_leads ?? 1;
                const pct = total > 0 ? Math.round((count / total) * 100) : 0;
                return (
                  <Card key={stage} size="sm">
                    <CardHeader>
                      <CardTitle className="text-sm">
                        {STAGE_LABELS[stage] ?? stage}
                      </CardTitle>
                      <CardDescription>{pct}% of total</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <p className="text-2xl font-bold">{count}</p>
                      <div className="mt-2 h-1.5 w-full rounded-full bg-muted">
                        <div
                          className="h-1.5 rounded-full bg-primary transition-all"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </CardContent>
                  </Card>
                );
              }
            )}
          </div>
        )}
      </div>
    </div>
  );
}
