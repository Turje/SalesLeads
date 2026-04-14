import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { OutreachGenerateRequest } from "@/lib/types";
import { toast } from "sonner";

export function useOutreachQueue(status?: string) {
  const params = status ? { status } : undefined;
  return useQuery({
    queryKey: ["outreach", "queue", status],
    queryFn: () => api.outreach.queue(params),
  });
}

export function useGmailStatus() {
  return useQuery({
    queryKey: ["gmail", "status"],
    queryFn: () => api.auth.gmailStatus(),
  });
}

export function useGenerateOutreach() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (req: OutreachGenerateRequest) => api.outreach.generate(req),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["outreach"] });
      toast.success(`Generated ${data.generated} drafts`);
      if (data.skipped.length > 0) {
        toast.info(`${data.skipped.length} leads skipped`);
      }
    },
    onError: (err) => {
      toast.error(`Generation failed: ${err instanceof Error ? err.message : "Unknown error"}`);
    },
  });
}

export function useApproveOutreach() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (ids: number[]) => api.outreach.approve(ids),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["outreach"] });
      toast.success(`${data.approved} messages approved`);
    },
  });
}

export function useEditOutreach() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...data }: { id: number; subject?: string; body?: string; status?: string }) =>
      api.outreach.editMessage(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["outreach"] });
    },
  });
}

export function useSendOutreach() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.outreach.send(),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["outreach"] });
      toast.success(`Sending ${data.total} emails...`);
    },
    onError: (err) => {
      toast.error(`Send failed: ${err instanceof Error ? err.message : "Unknown error"}`);
    },
  });
}

export function useSendStatus(jobId: string | null) {
  return useQuery({
    queryKey: ["outreach", "send-status", jobId],
    queryFn: () => api.outreach.sendStatus(jobId!),
    enabled: !!jobId,
    refetchInterval: (query) => {
      const data = query.state.data;
      return data?.status === "done" ? false : 2000;
    },
  });
}

export function useOutreachHistory(leadId: number) {
  return useQuery({
    queryKey: ["outreach", "history", leadId],
    queryFn: () => api.outreach.history(leadId),
    enabled: !!leadId,
  });
}
