import { usePipelineOverview } from "@/hooks/use-pipeline";
import { KanbanBoard } from "@/components/pipeline/kanban-board";
import { Skeleton } from "@/components/ui/skeleton";
import {
  CheckCircle,
  PhoneCall,
  CalendarCheck,
  FileText,
  CheckCircle2,
  Users,
} from "lucide-react";

const STAGE_CONFIG: Record<
  string,
  { label: string; color: string; icon: React.ElementType; description: string }
> = {
  APPROVED: {
    label: "Approved",
    color: "text-blue-400",
    icon: CheckCircle,
    description: "Ready to pursue",
  },
  CONTACTED: {
    label: "Contacted",
    color: "text-amber-400",
    icon: PhoneCall,
    description: "Outreach sent",
  },
  MEETING: {
    label: "Meeting",
    color: "text-purple-400",
    icon: CalendarCheck,
    description: "Meeting scheduled",
  },
  PROPOSAL: {
    label: "Proposal",
    color: "text-orange-400",
    icon: FileText,
    description: "Proposal sent",
  },
  CLOSED: {
    label: "Closed",
    color: "text-emerald-400",
    icon: CheckCircle2,
    description: "Deal won",
  },
};

export default function PipelinePage() {
  const { data: overview, isLoading } = usePipelineOverview();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">
          Pipeline
        </h1>
        <p className="text-sm text-muted-foreground">
          Drag approved leads through your sales pipeline. Click any card to view details.
        </p>
      </div>

      {/* Stage summary bar */}
      <div className="flex items-center gap-1 rounded-lg border border-border bg-card p-3">
        <div className="flex items-center gap-2 pr-4 border-r border-border">
          <Users className="size-4 text-muted-foreground" />
          <div>
            <p className="text-lg font-bold leading-none">
              {isLoading ? (
                <Skeleton className="h-5 w-8 inline-block" />
              ) : (
                overview?.total ?? 0
              )}
            </p>
            <p className="text-[11px] text-muted-foreground">Total</p>
          </div>
        </div>

        <div className="flex flex-1 items-center justify-around">
          {Object.entries(STAGE_CONFIG).map(([stage, config]) => {
            const count =
              !isLoading && overview?.stages
                ? overview.stages[stage] ?? 0
                : 0;
            const Icon = config.icon;
            return (
              <div key={stage} className="flex items-center gap-2 px-3">
                <Icon className={`size-4 ${config.color}`} />
                <div>
                  <p className="text-sm font-semibold leading-none">
                    {isLoading ? (
                      <Skeleton className="h-4 w-5 inline-block" />
                    ) : (
                      count
                    )}
                  </p>
                  <p className="text-[11px] text-muted-foreground">
                    {config.label}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <KanbanBoard stageConfig={STAGE_CONFIG} />
    </div>
  );
}
