import { useState } from "react";
import { useLeads } from "@/hooks/use-leads";
import { LeadCard } from "@/components/leads/lead-card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const BOROUGHS = [
  { value: "", label: "All Boroughs" },
  { value: "Manhattan", label: "Manhattan" },
  { value: "Brooklyn", label: "Brooklyn" },
  { value: "Queens", label: "Queens" },
  { value: "Bronx", label: "Bronx" },
  { value: "Staten Island", label: "Staten Island" },
];

const STAGES: { value: string; label: string }[] = [
  { value: "", label: "All Stages" },
  { value: "NEW", label: "New" },
  { value: "APPROVED", label: "Approved" },
  { value: "CONTACTED", label: "Contacted" },
  { value: "MEETING", label: "Meeting" },
  { value: "PROPOSAL", label: "Proposal" },
  { value: "CONTRACT_SIGNED", label: "Contract Signed" },
  { value: "CLOSED", label: "Closed" },
  { value: "DISAPPROVED", label: "Disapproved" },
];

export default function LeadsPage() {
  const [borough, setBorough] = useState("");
  const [stage, setStage] = useState("");

  const params: Record<string, string | number> = { page: 1, page_size: 200 };
  if (borough) params.borough = borough;
  if (stage) params.pipeline_stage = stage;

  const { data, isLoading } = useLeads(params);
  const leads = data?.items ?? [];

  // Sort newest first so old leads go to the end
  const sorted = [...leads].sort(
    (a, b) => new Date(b.discovery_date).getTime() - new Date(a.discovery_date).getTime()
  );

  // Count leads per borough for badge counts
  const allLeads = data?.items ?? [];
  const boroughCounts: Record<string, number> = {};
  for (const l of allLeads) {
    boroughCounts[l.borough] = (boroughCounts[l.borough] ?? 0) + 1;
  }

  const newCount = allLeads.filter((l) => l.pipeline_stage === "NEW").length;

  return (
    <div className="flex flex-col gap-4">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Leads</h1>
          <p className="text-sm text-muted-foreground">
            {isLoading ? "Loading..." : `${data?.total ?? 0} leads`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {!isLoading && newCount > 0 && (
            <Badge variant="secondary" className="px-3 py-1 text-sm">
              {newCount} awaiting review
            </Badge>
          )}
          <Select value={stage} onValueChange={(v) => setStage(v ?? "")}>
            <SelectTrigger className="w-[150px]">
              <SelectValue placeholder="All Stages" />
            </SelectTrigger>
            <SelectContent>
              {STAGES.map((s) => (
                <SelectItem key={s.value} value={s.value}>
                  {s.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Borough Tabs */}
      <Tabs value={borough} onValueChange={setBorough}>
        <TabsList className="w-full justify-start">
          {BOROUGHS.map((b) => (
            <TabsTrigger key={b.value} value={b.value} className="gap-2">
              {b.label}
              {!isLoading && (
                <Badge variant="secondary" className="ml-1 h-5 min-w-[20px] px-1.5 text-xs">
                  {b.value === ""
                    ? data?.total ?? 0
                    : boroughCounts[b.value] ?? 0}
                </Badge>
              )}
            </TabsTrigger>
          ))}
        </TabsList>

        {/* Single content area for all tabs */}
        {BOROUGHS.map((b) => (
          <TabsContent key={b.value} value={b.value}>
            {isLoading ? (
              <div className="grid gap-4 pt-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {Array.from({ length: 8 }).map((_, i) => (
                  <Skeleton key={i} className="h-48 w-full rounded-lg" />
                ))}
              </div>
            ) : sorted.length === 0 ? (
              <div className="flex items-center justify-center py-20">
                <p className="text-muted-foreground">
                  No leads found{b.value ? ` in ${b.label}` : ""}
                  {stage ? ` with stage ${stage.toLowerCase()}` : ""}
                </p>
              </div>
            ) : (
              <div className="grid gap-4 pt-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {sorted.map((lead) => (
                  <LeadCard key={lead.id} lead={lead} />
                ))}
              </div>
            )}
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}
