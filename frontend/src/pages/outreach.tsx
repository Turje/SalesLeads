import { useState, useEffect, useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useLeads } from "@/hooks/use-leads";
import {
  useOutreachQueue,
  useGmailStatus,
  useGenerateOutreach,
  useApproveOutreach,
  useEditOutreach,
  useSendOutreach,
  useSendStatus,
} from "@/hooks/use-outreach";
import { api } from "@/lib/api";
import type { OutreachMessage, OutreachGenerateRequest } from "@/lib/types";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";
import {
  Send,
  Mail,
  CheckCircle2,
  XCircle,
  Clock,
  ChevronDown,
  ChevronUp,
  Loader2,
  SparklesIcon,
  Check,
  Trash2,
} from "lucide-react";

const TEMPLATES: { value: OutreachGenerateRequest["template"]; label: string }[] = [
  { value: "initial_outreach", label: "Initial Outreach" },
  { value: "follow_up", label: "Follow Up" },
  { value: "meeting_request", label: "Meeting Request" },
];

const STATUS_BADGE: Record<string, { variant: "default" | "secondary" | "destructive" | "outline"; label: string }> = {
  draft: { variant: "secondary", label: "Draft" },
  approved: { variant: "default", label: "Approved" },
  sending: { variant: "default", label: "Sending" },
  sent: { variant: "outline", label: "Sent" },
  failed: { variant: "destructive", label: "Failed" },
  discarded: { variant: "secondary", label: "Discarded" },
};

export default function OutreachPage() {
  // ── Lead selector state ──
  const [template, setTemplate] =
    useState<OutreachGenerateRequest["template"]>("initial_outreach");
  const [selectedLeadIds, setSelectedLeadIds] = useState<Set<number>>(new Set());

  // ── Queue state ──
  const [statusFilter, setStatusFilter] = useState("all");
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [editSubject, setEditSubject] = useState("");
  const [editBody, setEditBody] = useState("");

  // ── Send state ──
  const [jobId, setJobId] = useState<string | null>(null);

  // ── Data hooks ──
  const { data: leadsData, isLoading: leadsLoading } = useLeads({ page_size: 200 });
  const { data: gmailData } = useGmailStatus();
  const queueStatus = statusFilter === "all" ? undefined : statusFilter;
  const { data: queueData, isLoading: queueLoading } = useOutreachQueue(queueStatus);
  const { data: sendStatusData } = useSendStatus(jobId);

  // ── Mutations ──
  const generateMutation = useGenerateOutreach();
  const approveMutation = useApproveOutreach();
  const editMutation = useEditOutreach();
  const sendMutation = useSendOutreach();

  const queryClient = useQueryClient();

  // ── Gmail OAuth listener ──
  useEffect(() => {
    const handler = (event: MessageEvent) => {
      if (event.data?.gmail === "connected") {
        queryClient.invalidateQueries({ queryKey: ["gmail"] });
      }
    };
    window.addEventListener("message", handler);
    return () => window.removeEventListener("message", handler);
  }, [queryClient]);

  // ── Clear jobId when send is done ──
  useEffect(() => {
    if (sendStatusData?.status === "done") {
      queryClient.invalidateQueries({ queryKey: ["outreach"] });
      if (sendStatusData.failed > 0) {
        toast.error(`${sendStatusData.failed} emails failed to send`);
      } else {
        toast.success(`All ${sendStatusData.sent} emails sent successfully`);
      }
      setJobId(null);
    }
  }, [sendStatusData, queryClient]);

  // ── Lead selection helpers ──
  const toggleLead = useCallback((id: number) => {
    setSelectedLeadIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const selectAll = useCallback(() => {
    if (!leadsData) return;
    setSelectedLeadIds(new Set(leadsData.items.map((l) => l.id)));
  }, [leadsData]);

  const deselectAll = useCallback(() => {
    setSelectedLeadIds(new Set());
  }, []);

  // ── Generate ──
  const handleGenerate = () => {
    if (selectedLeadIds.size === 0) {
      toast.error("Select at least one lead");
      return;
    }
    generateMutation.mutate({
      lead_ids: Array.from(selectedLeadIds),
      template,
    });
  };

  // ── Expand card ──
  const handleExpand = (msg: OutreachMessage) => {
    if (expandedId === msg.id) {
      setExpandedId(null);
    } else {
      setExpandedId(msg.id);
      setEditSubject(msg.subject);
      setEditBody(msg.body);
    }
  };

  // ── Save edits ──
  const handleSaveEdit = (id: number) => {
    editMutation.mutate(
      { id, subject: editSubject, body: editBody },
      { onSuccess: () => toast.success("Draft updated") }
    );
  };

  // ── Discard ──
  const handleDiscard = (id: number) => {
    editMutation.mutate(
      { id, status: "discarded" },
      { onSuccess: () => toast.success("Draft discarded") }
    );
  };

  // ── Approve single ──
  const handleApprove = (id: number) => {
    approveMutation.mutate([id]);
  };

  // ── Approve all drafts ──
  const handleApproveAll = () => {
    const draftIds = queueData?.items
      .filter((m) => m.status === "draft")
      .map((m) => m.id) ?? [];
    if (draftIds.length === 0) {
      toast.info("No drafts to approve");
      return;
    }
    approveMutation.mutate(draftIds);
  };

  // ── Gmail connect ──
  const connectGmail = async () => {
    try {
      const { auth_url } = await api.auth.gmailAuthUrl();
      window.open(auth_url, "gmail-auth", "width=500,height=600");
    } catch {
      toast.error("Failed to get Gmail auth URL");
    }
  };

  const disconnectGmail = async () => {
    try {
      await api.auth.gmailDisconnect();
      queryClient.invalidateQueries({ queryKey: ["gmail"] });
      toast.success("Gmail disconnected");
    } catch {
      toast.error("Failed to disconnect");
    }
  };

  // ── Send approved ──
  const handleSend = () => {
    sendMutation.mutate(undefined, {
      onSuccess: (data) => setJobId(data.job_id),
    });
  };

  // ── Counts ──
  const approvedCount = queueData?.items.filter((m) => m.status === "approved").length ?? 0;
  const draftCount = queueData?.items.filter((m) => m.status === "draft").length ?? 0;
  const gmailConnected = gmailData?.connected ?? false;

  return (
    <div className="space-y-6">
      {/* ── Page header + Gmail status ── */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">
            Outreach
          </h1>
          <p className="text-sm text-muted-foreground">
            Generate, review, and send outreach emails in bulk.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {gmailConnected ? (
            <div className="flex items-center gap-2 text-sm">
              <span className="inline-block size-2 rounded-full bg-green-500" />
              <span className="text-muted-foreground">{gmailData?.email}</span>
              <button
                onClick={disconnectGmail}
                className="text-xs text-muted-foreground underline hover:text-foreground"
              >
                Disconnect
              </button>
            </div>
          ) : (
            <Button variant="outline" size="sm" onClick={connectGmail}>
              <Mail className="size-4" />
              Connect Gmail
            </Button>
          )}

          <Button
            size="sm"
            disabled={approvedCount === 0 || !gmailConnected || sendMutation.isPending || !!jobId}
            onClick={handleSend}
          >
            {sendMutation.isPending || jobId ? (
              <>
                <Loader2 className="size-4 animate-spin" />
                {jobId && sendStatusData
                  ? `${sendStatusData.sent}/${sendStatusData.total}`
                  : "Starting..."}
              </>
            ) : (
              <>
                <Send className="size-4" />
                Send Approved ({approvedCount})
              </>
            )}
          </Button>
        </div>
      </div>

      {/* ── Section 1: Lead Selector ── */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Generate Drafts</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-end gap-4">
            <div className="w-64 space-y-1">
              <span className="text-xs font-medium text-muted-foreground">Template</span>
              <Select
                value={template}
                onValueChange={(v) => setTemplate(v as OutreachGenerateRequest["template"])}
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {TEMPLATES.map((t) => (
                    <SelectItem key={t.value} value={t.value}>
                      {t.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={selectAll}>
                Select All
              </Button>
              <Button variant="outline" size="sm" onClick={deselectAll}>
                Deselect All
              </Button>
            </div>

            <Button
              onClick={handleGenerate}
              disabled={selectedLeadIds.size === 0 || generateMutation.isPending}
              className="ml-auto"
            >
              {generateMutation.isPending ? (
                <>
                  <Loader2 className="size-4 animate-spin" />
                  Generating...
                </>
              ) : (
                <>
                  <SparklesIcon className="size-4" />
                  Generate Drafts ({selectedLeadIds.size})
                </>
              )}
            </Button>
          </div>

          {/* Lead checkboxes */}
          {leadsLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-6 w-full" />
              <Skeleton className="h-6 w-full" />
              <Skeleton className="h-6 w-3/4" />
            </div>
          ) : (
            <div className="grid max-h-48 gap-1 overflow-y-auto rounded-md border border-border p-2 sm:grid-cols-2 lg:grid-cols-3">
              {leadsData?.items.map((lead) => {
                const selected = selectedLeadIds.has(lead.id);
                return (
                  <button
                    key={lead.id}
                    type="button"
                    onClick={() => toggleLead(lead.id)}
                    className={`flex items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm transition-colors ${
                      selected
                        ? "bg-primary/10 text-foreground"
                        : "text-muted-foreground hover:bg-muted"
                    }`}
                  >
                    <span
                      className={`flex size-4 shrink-0 items-center justify-center rounded border ${
                        selected
                          ? "border-primary bg-primary text-primary-foreground"
                          : "border-muted-foreground/40"
                      }`}
                    >
                      {selected && <Check className="size-3" />}
                    </span>
                    <span className="truncate">
                      {lead.company_name}
                      {lead.contact_name ? ` - ${lead.contact_name}` : ""}
                    </span>
                    {lead.email && (
                      <span className="ml-auto truncate text-xs text-muted-foreground/60">
                        {lead.email}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          )}

          {/* Generation summary */}
          {generateMutation.data && (
            <p className="text-sm text-muted-foreground">
              Generated {generateMutation.data.generated} drafts
              {generateMutation.data.skipped.length > 0 &&
                `, ${generateMutation.data.skipped.length} skipped`}
            </p>
          )}
        </CardContent>
      </Card>

      {/* ── Section 2: Draft Queue ── */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-foreground">Draft Queue</h2>
          {draftCount > 0 && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleApproveAll}
              disabled={approveMutation.isPending}
            >
              <CheckCircle2 className="size-4" />
              Approve All Drafts ({draftCount})
            </Button>
          )}
        </div>

        <Tabs value={statusFilter} onValueChange={setStatusFilter}>
          <TabsList>
            <TabsTrigger value="all">All</TabsTrigger>
            <TabsTrigger value="draft">Drafts</TabsTrigger>
            <TabsTrigger value="approved">Approved</TabsTrigger>
            <TabsTrigger value="sent">Sent</TabsTrigger>
            <TabsTrigger value="failed">Failed</TabsTrigger>
          </TabsList>

          {/* Single content area for all tabs since filtering is via query param */}
          <TabsContent value={statusFilter} className="mt-4">
            {queueLoading ? (
              <div className="space-y-3">
                <Skeleton className="h-20 w-full" />
                <Skeleton className="h-20 w-full" />
                <Skeleton className="h-20 w-full" />
              </div>
            ) : !queueData?.items.length ? (
              <div className="flex min-h-[200px] items-center justify-center rounded-lg border border-dashed border-border">
                <p className="text-sm text-muted-foreground">
                  No messages{statusFilter !== "all" ? ` with status "${statusFilter}"` : ""}. Generate some drafts above.
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                {queueData.items.map((msg) => {
                  const isExpanded = expandedId === msg.id;
                  const badgeInfo = STATUS_BADGE[msg.status] ?? STATUS_BADGE.draft;
                  return (
                    <Card key={msg.id} className="overflow-hidden">
                      <button
                        type="button"
                        onClick={() => handleExpand(msg)}
                        className="flex w-full items-center gap-3 px-4 py-3 text-left"
                      >
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <span className="truncate text-sm font-medium text-foreground">
                              {msg.to_name ?? "Unknown"}
                            </span>
                            <Badge variant={badgeInfo.variant} className="text-xs">
                              {badgeInfo.label}
                            </Badge>
                          </div>
                          <p className="truncate text-xs text-muted-foreground">
                            {msg.subject}
                          </p>
                          {msg.to_email && (
                            <p className="text-xs text-muted-foreground/60">
                              {msg.to_email}
                            </p>
                          )}
                        </div>
                        {isExpanded ? (
                          <ChevronUp className="size-4 shrink-0 text-muted-foreground" />
                        ) : (
                          <ChevronDown className="size-4 shrink-0 text-muted-foreground" />
                        )}
                      </button>

                      {isExpanded && (
                        <CardContent className="space-y-3 border-t border-border pt-3">
                          <div className="space-y-1">
                            <span className="text-xs font-medium text-muted-foreground">Subject</span>
                            <Input
                              value={editSubject}
                              onChange={(e) => setEditSubject(e.target.value)}
                              disabled={msg.status !== "draft"}
                            />
                          </div>
                          <div className="space-y-1">
                            <span className="text-xs font-medium text-muted-foreground">Body</span>
                            <Textarea
                              value={editBody}
                              onChange={(e) => setEditBody(e.target.value)}
                              className="min-h-[200px]"
                              disabled={msg.status !== "draft"}
                            />
                          </div>

                          {msg.error_message && (
                            <p className="text-xs text-destructive">
                              Error: {msg.error_message}
                            </p>
                          )}

                          {msg.status === "draft" && (
                            <div className="flex gap-2">
                              <Button
                                size="sm"
                                onClick={() => handleSaveEdit(msg.id)}
                                disabled={editMutation.isPending}
                              >
                                Save Edits
                              </Button>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => handleApprove(msg.id)}
                                disabled={approveMutation.isPending}
                              >
                                <CheckCircle2 className="size-4" />
                                Approve
                              </Button>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => handleDiscard(msg.id)}
                                disabled={editMutation.isPending}
                              >
                                <Trash2 className="size-4" />
                                Discard
                              </Button>
                            </div>
                          )}

                          {msg.status === "sent" && msg.sent_at && (
                            <p className="flex items-center gap-1 text-xs text-muted-foreground">
                              <CheckCircle2 className="size-3 text-green-500" />
                              Sent {new Date(msg.sent_at).toLocaleString()}
                            </p>
                          )}

                          {msg.status === "failed" && (
                            <p className="flex items-center gap-1 text-xs text-destructive">
                              <XCircle className="size-3" />
                              {msg.error_message ?? "Send failed"}
                            </p>
                          )}

                          {msg.status === "approved" && (
                            <p className="flex items-center gap-1 text-xs text-muted-foreground">
                              <Clock className="size-3" />
                              Approved — waiting to send
                            </p>
                          )}
                        </CardContent>
                      )}
                    </Card>
                  );
                })}
              </div>
            )}
          </TabsContent>
        </Tabs>
      </div>

      {/* ── Send progress ── */}
      {jobId && sendStatusData && sendStatusData.status === "running" && (
        <Card>
          <CardContent className="flex items-center gap-3 py-4">
            <Loader2 className="size-4 animate-spin text-primary" />
            <span className="text-sm text-foreground">
              Sending: {sendStatusData.sent} / {sendStatusData.total} emails
            </span>
            <div className="ml-auto h-2 w-48 overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-primary transition-all"
                style={{
                  width: `${sendStatusData.total > 0 ? (sendStatusData.sent / sendStatusData.total) * 100 : 0}%`,
                }}
              />
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
