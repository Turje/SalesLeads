import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useAgentStatus() {
  return useQuery({
    queryKey: ["agents", "status"],
    queryFn: () => api.agents.status(),
    refetchInterval: 30000,
  });
}

export function useTriggerAgents() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.agents.trigger(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["agents"] });
    },
  });
}
