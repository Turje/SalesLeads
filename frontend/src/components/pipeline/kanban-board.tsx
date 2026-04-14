import { useCallback, useMemo } from "react";
import { DragDropContext, type DropResult } from "@hello-pangea/dnd";
import { useQueryClient } from "@tanstack/react-query";
import { usePipelineStage } from "@/hooks/use-pipeline";
import { api } from "@/lib/api";
import { KanbanColumn } from "./kanban-column";
import { Skeleton } from "@/components/ui/skeleton";
import type { PipelineStage } from "@/lib/types";

interface StageInfo {
  label: string;
  color: string;
  icon: React.ElementType;
  description: string;
}

interface KanbanBoardProps {
  stageConfig: Record<string, StageInfo>;
}

export function KanbanBoard({ stageConfig }: KanbanBoardProps) {
  const queryClient = useQueryClient();
  const stages = useMemo(
    () => Object.keys(stageConfig) as PipelineStage[],
    [stageConfig]
  );

  // We need a fixed number of hooks, so query all possible stages
  const approved = usePipelineStage("APPROVED");
  const contacted = usePipelineStage("CONTACTED");
  const meeting = usePipelineStage("MEETING");
  const proposal = usePipelineStage("PROPOSAL");
  const contractSigned = usePipelineStage("CONTRACT_SIGNED");
  const closed = usePipelineStage("CLOSED");

  const stageQueryMap: Record<string, typeof approved> = {
    APPROVED: approved,
    CONTACTED: contacted,
    MEETING: meeting,
    PROPOSAL: proposal,
    CONTRACT_SIGNED: contractSigned,
    CLOSED: closed,
  };

  const isLoading = stages.some((s) => stageQueryMap[s]?.isLoading);

  const handleDragEnd = useCallback(
    async (result: DropResult) => {
      const { draggableId, destination, source } = result;

      if (!destination) return;
      if (
        destination.droppableId === source.droppableId &&
        destination.index === source.index
      ) {
        return;
      }

      const leadId = Number(draggableId);
      const newStage = destination.droppableId;

      try {
        await api.leads.updateStage(leadId, newStage);
        queryClient.invalidateQueries({ queryKey: ["pipeline"] });
        queryClient.invalidateQueries({ queryKey: ["leads"] });
      } catch {
        queryClient.invalidateQueries({ queryKey: ["pipeline"] });
      }
    },
    [queryClient]
  );

  if (isLoading) {
    return (
      <div className="flex gap-4 overflow-x-auto pb-4">
        {stages.map((stage) => (
          <div
            key={stage}
            className="flex w-80 shrink-0 flex-col gap-2 rounded-lg bg-muted/50 border border-border p-3"
          >
            <Skeleton className="h-6 w-24" />
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-24 w-full" />
          </div>
        ))}
      </div>
    );
  }

  return (
    <DragDropContext onDragEnd={handleDragEnd}>
      <div className="flex gap-4 overflow-x-auto pb-4">
        {stages.map((stage) => {
          const config = stageConfig[stage];
          const query = stageQueryMap[stage];
          return (
            <KanbanColumn
              key={stage}
              stage={stage}
              leads={query?.data ?? []}
              label={config?.label ?? stage}
              color={config?.color ?? "text-foreground"}
              icon={config?.icon}
              description={config?.description ?? ""}
            />
          );
        })}
      </div>
    </DragDropContext>
  );
}
