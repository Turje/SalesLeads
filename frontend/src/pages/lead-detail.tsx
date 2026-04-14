import { useParams, useNavigate } from "react-router-dom";
import { useLead, useUpdateStage } from "@/hooks/use-leads";
import { ContactSection } from "@/components/detail/contact-section";
import { PropertySection } from "@/components/detail/property-section";
import { BuildingSummarySection } from "@/components/detail/building-summary-section";
import { ISPSection } from "@/components/detail/isp-section";
import { EquipmentSection } from "@/components/detail/equipment-section";
import { IntelligenceSection } from "@/components/detail/intelligence-section";
import { NotesSection } from "@/components/detail/notes-section";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ArrowLeft, ThumbsUp, ThumbsDown } from "lucide-react";
import { toast } from "sonner";
import type { PipelineStage } from "@/lib/types";

const STAGES: PipelineStage[] = [
  "NEW",
  "APPROVED",
  "CONTACTED",
  "MEETING",
  "PROPOSAL",
  "CONTRACT_SIGNED",
  "CLOSED",
  "DISAPPROVED",
];

export default function LeadDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const leadId = Number(id);
  const { data: lead, isLoading } = useLead(leadId);
  const updateStage = useUpdateStage();

  const handleStageChange = (newStage: string | null) => {
    if (!newStage) return;
    updateStage.mutate(
      { id: leadId, stage: newStage },
      {
        onSuccess: () => {
          toast.success(`Stage updated to ${newStage.charAt(0) + newStage.slice(1).toLowerCase()}`);
        },
        onError: () => {
          toast.error("Failed to update stage");
        },
      }
    );
  };

  if (isLoading) {
    return (
      <div className="flex flex-col gap-6">
        <div className="flex items-center gap-4">
          <Skeleton className="h-8 w-8" />
          <Skeleton className="h-8 w-64" />
        </div>
        <Skeleton className="h-10 w-96" />
        <div className="grid gap-6 lg:grid-cols-2">
          <Skeleton className="h-64 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      </div>
    );
  }

  if (!lead) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-20">
        <p className="text-lg text-muted-foreground">Lead not found</p>
        <Button variant="outline" onClick={() => navigate("/")}>
          <ArrowLeft className="size-4" />
          Back to Leads
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex flex-col gap-4">
        <Button
          variant="ghost"
          size="sm"
          className="w-fit"
          onClick={() => navigate("/")}
        >
          <ArrowLeft className="size-4" />
          Back to Leads
        </Button>

        <div className="flex flex-wrap items-center gap-4">
          <h1 className="text-2xl font-bold text-foreground">
            {lead.company_name}
          </h1>

          <div className="ml-auto flex items-center gap-2">
            {lead.pipeline_stage === "NEW" && (
              <>
                <Button
                  variant="outline"
                  size="sm"
                  className="text-emerald-500 border-emerald-500/30 hover:bg-emerald-500/10"
                  onClick={() => handleStageChange("APPROVED")}
                >
                  <ThumbsUp className="size-4" />
                  Approve
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="text-red-500 border-red-500/30 hover:bg-red-500/10"
                  onClick={() => handleStageChange("DISAPPROVED")}
                >
                  <ThumbsDown className="size-4" />
                  Reject
                </Button>
              </>
            )}
            <span className="text-sm text-muted-foreground">Stage:</span>
            <Select
              value={lead.pipeline_stage}
              onValueChange={handleStageChange}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {STAGES.map((s) => (
                  <SelectItem key={s} value={s}>
                    {s.charAt(0) + s.slice(1).toLowerCase()}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="building">Building</TabsTrigger>
          <TabsTrigger value="intelligence">Intelligence</TabsTrigger>
          <TabsTrigger value="notes">Notes</TabsTrigger>
        </TabsList>

        <TabsContent value="overview">
          <div className="grid gap-6 pt-4 lg:grid-cols-2">
            <ContactSection lead={lead} />
            <PropertySection lead={lead} />
          </div>
        </TabsContent>

        <TabsContent value="building">
          <div className="flex flex-col gap-6 pt-4">
            <BuildingSummarySection summary={lead.building_summary} />
            <div className="grid gap-6 lg:grid-cols-2">
              <ISPSection lead={lead} />
              <EquipmentSection lead={lead} />
            </div>
          </div>
        </TabsContent>

        <TabsContent value="intelligence">
          <div className="pt-4">
            <IntelligenceSection lead={lead} />
          </div>
        </TabsContent>

        <TabsContent value="notes">
          <div className="pt-4">
            <NotesSection leadId={lead.id} notes={lead.qualification_notes} />
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
