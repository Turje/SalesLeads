import { useState } from "react";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";
import { Loader2Icon, CopyIcon, SparklesIcon } from "lucide-react";
import type { EmailDraftRequest, EmailDraftResponse } from "@/lib/types";

const TEMPLATES: { value: EmailDraftRequest["template"]; label: string }[] = [
  { value: "initial_outreach", label: "Initial Outreach" },
  { value: "follow_up", label: "Follow Up" },
  { value: "meeting_request", label: "Meeting Request" },
];

export default function EmailPage() {
  const [leadId, setLeadId] = useState<number | null>(null);
  const [template, setTemplate] =
    useState<EmailDraftRequest["template"]>("initial_outreach");
  const [draft, setDraft] = useState<EmailDraftResponse | null>(null);
  const [editedBody, setEditedBody] = useState("");

  const { data: leadsData, isLoading: leadsLoading } = useLeads({
    page_size: 200,
  });

  const draftMutation = useMutation({
    mutationFn: (req: EmailDraftRequest) => api.email.draft(req),
    onSuccess: (data) => {
      setDraft(data);
      setEditedBody(data.body);
      toast.success("Email draft generated");
    },
    onError: (error) => {
      toast.error(
        `Failed to generate draft: ${error instanceof Error ? error.message : "Unknown error"}`
      );
    },
  });

  const handleGenerate = () => {
    if (!leadId) {
      toast.error("Please select a lead");
      return;
    }
    draftMutation.mutate({ lead_id: leadId, template });
  };

  const handleCopy = async () => {
    const text = draft
      ? `Subject: ${draft.subject}\n\n${editedBody}`
      : editedBody;
    try {
      await navigator.clipboard.writeText(text);
      toast.success("Copied to clipboard");
    } catch {
      toast.error("Failed to copy");
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">
          Email Drafter
        </h1>
        <p className="text-sm text-muted-foreground">
          Generate personalized outreach emails for your leads.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Compose</CardTitle>
            <CardDescription>
              Select a lead and template to generate an email draft.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="lead-select">Lead</Label>
              {leadsLoading ? (
                <Skeleton className="h-8 w-full" />
              ) : (
                <Select
                  value={leadId !== null ? String(leadId) : undefined}
                  onValueChange={(val) => setLeadId(Number(val))}
                >
                  <SelectTrigger className="w-full" id="lead-select">
                    <SelectValue placeholder="Select a lead..." />
                  </SelectTrigger>
                  <SelectContent>
                    {leadsData?.items.map((lead) => (
                      <SelectItem key={lead.id} value={String(lead.id)}>
                        {lead.company_name} - {lead.contact_name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="template-select">Template</Label>
              <Select
                value={template}
                onValueChange={(val) =>
                  setTemplate(val as EmailDraftRequest["template"])
                }
              >
                <SelectTrigger className="w-full" id="template-select">
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

            <Button
              onClick={handleGenerate}
              disabled={!leadId || draftMutation.isPending}
              className="w-full"
            >
              {draftMutation.isPending ? (
                <>
                  <Loader2Icon className="size-4 animate-spin" />
                  Generating...
                </>
              ) : (
                <>
                  <SparklesIcon className="size-4" />
                  Generate Draft
                </>
              )}
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Preview</CardTitle>
            {draft && (
              <CardDescription>
                Generated in {draft.duration_ms}ms using {draft.model}
              </CardDescription>
            )}
          </CardHeader>
          <CardContent className="space-y-4">
            {draft ? (
              <>
                <div className="space-y-2">
                  <Label>Subject</Label>
                  <p className="text-sm font-medium rounded-lg border border-border bg-muted/50 px-3 py-2">
                    {draft.subject}
                  </p>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="email-body">Body</Label>
                  <Textarea
                    id="email-body"
                    value={editedBody}
                    onChange={(e) => setEditedBody(e.target.value)}
                    className="min-h-[280px]"
                  />
                </div>
                <Button variant="outline" onClick={handleCopy} className="w-full">
                  <CopyIcon className="size-4" />
                  Copy to Clipboard
                </Button>
              </>
            ) : (
              <div className="flex min-h-[300px] items-center justify-center rounded-lg border border-dashed border-border">
                <p className="text-sm text-muted-foreground">
                  {draftMutation.isPending
                    ? "Generating your email..."
                    : "Select a lead and click Generate to create a draft."}
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
