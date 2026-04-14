import { useNavigate } from "react-router-dom";
import { useUpdateStage } from "@/hooks/use-leads";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Building2,
  User,
  MapPin,
  Mail,
  ThumbsUp,
  ThumbsDown,
} from "lucide-react";
import { toast } from "sonner";
import type { Lead } from "@/lib/types";

const STAGE_COLORS: Record<string, string> = {
  NEW: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  APPROVED: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  CONTACTED: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  MEETING: "bg-purple-500/10 text-purple-400 border-purple-500/20",
  PROPOSAL: "bg-orange-500/10 text-orange-400 border-orange-500/20",
  CONTRACT_SIGNED: "bg-teal-500/10 text-teal-400 border-teal-500/20",
  CLOSED: "bg-green-500/10 text-green-400 border-green-500/20",
  DISAPPROVED: "bg-red-500/10 text-red-400 border-red-500/20",
};

export function LeadCard({ lead }: { lead: Lead }) {
  const navigate = useNavigate();
  const updateStage = useUpdateStage();

  const handleApprove = (e: React.MouseEvent) => {
    e.stopPropagation();
    updateStage.mutate(
      { id: lead.id, stage: "APPROVED" },
      {
        onSuccess: () => toast.success(`${lead.company_name} approved`),
        onError: () => toast.error("Failed to update"),
      }
    );
  };

  const handleReject = (e: React.MouseEvent) => {
    e.stopPropagation();
    updateStage.mutate(
      { id: lead.id, stage: "DISAPPROVED" },
      {
        onSuccess: () => toast.success(`${lead.company_name} rejected`),
        onError: () => toast.error("Failed to update"),
      }
    );
  };

  return (
    <Card
      className="cursor-pointer transition-all hover:border-primary/40 hover:shadow-md hover:shadow-primary/5"
      onClick={() => navigate(`/leads/${lead.id}`)}
    >
      <CardContent className="flex flex-col gap-3 p-4">
        <div className="flex items-start justify-between gap-2">
          <h3 className="font-semibold text-foreground leading-tight">
            {lead.company_name}
          </h3>
          <Badge
            variant="outline"
            className={`shrink-0 text-xs ${STAGE_COLORS[lead.pipeline_stage] ?? ""}`}
          >
            {lead.pipeline_stage.charAt(0) + lead.pipeline_stage.slice(1).toLowerCase()}
          </Badge>
        </div>

        <div className="flex flex-col gap-1.5 text-sm text-muted-foreground">
          <div className="flex items-center gap-2">
            <User className="size-3.5 shrink-0" />
            <span className="truncate">
              {lead.contact_name}
              {lead.contact_title && (
                <span className="text-muted-foreground/60"> — {lead.contact_title}</span>
              )}
            </span>
          </div>

          <div className="flex items-center gap-2">
            <MapPin className="size-3.5 shrink-0" />
            <span className="truncate">{lead.neighborhood}</span>
          </div>

          <div className="flex items-center gap-2">
            <Building2 className="size-3.5 shrink-0" />
            <span className="truncate">
              {lead.building_type}
              {lead.sqft ? ` · ${(lead.sqft / 1000).toFixed(0)}K sqft` : ""}
            </span>
          </div>

          {lead.email && (
            <div className="flex items-center gap-2">
              <Mail className="size-3.5 shrink-0" />
              <span className="truncate text-xs">{lead.email}</span>
            </div>
          )}
        </div>

        {lead.pipeline_stage === "NEW" && (
          <div className="flex items-center gap-2 pt-1 border-t border-border">
            <Button
              variant="ghost"
              size="sm"
              className="flex-1 text-emerald-500 hover:text-emerald-400 hover:bg-emerald-500/10"
              onClick={handleApprove}
              disabled={updateStage.isPending}
            >
              <ThumbsUp className="size-3.5" />
              Approve
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="flex-1 text-red-500 hover:text-red-400 hover:bg-red-500/10"
              onClick={handleReject}
              disabled={updateStage.isPending}
            >
              <ThumbsDown className="size-3.5" />
              Reject
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
