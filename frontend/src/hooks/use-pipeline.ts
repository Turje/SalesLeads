import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function usePipelineOverview() {
  return useQuery({
    queryKey: ["pipeline", "overview"],
    queryFn: () => api.pipeline.overview(),
  });
}

export function usePipelineStage(stage: string) {
  return useQuery({
    queryKey: ["pipeline", "stage", stage],
    queryFn: () => api.pipeline.stage(stage),
    enabled: !!stage,
  });
}
