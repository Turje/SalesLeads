import { useState } from "react";
import { useLeads } from "@/hooks/use-leads";
import { LeadCard } from "@/components/leads/lead-card";
import { LeadFilters } from "@/components/leads/lead-filters";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { SlidersHorizontal } from "lucide-react";

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
  const [filters, setFilters] = useState<Record<string, string | number>>({});
  const [filtersOpen, setFiltersOpen] = useState(false);

  const params: Record<string, string | number> = { page: 1, page_size: 200 };
  if (borough) params.borough = borough;
  if (stage) params.pipeline_stage = stage;
  // Merge in advanced filters
  for (const [k, v] of Object.entries(filters)) {
    if (v) params[k] = v;
  }

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
  const activeFilterCount = Object.values(filters).filter(Boolean).length;

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
            <Badge variant="secondary" className="hidden px-3 py-1 text-sm sm:inline-flex">
              {newCount} awaiting review
            </Badge>
          )}

          {/* Filter button — opens sheet with full filters */}
          <Button variant="outline" size="sm" className="gap-2" onClick={() => setFiltersOpen(true)}>
            <SlidersHorizontal className="size-4" />
            <span className="hidden sm:inline">Filters</span>
            {activeFilterCount > 0 && (
              <Badge variant="secondary" className="h-5 min-w-[20px] px-1.5 text-xs">
                {activeFilterCount}
              </Badge>
            )}
          </Button>
          <Sheet open={filtersOpen} onOpenChange={setFiltersOpen}>
            <SheetContent side="right" className="w-[300px] sm:w-[360px]">
              <SheetHeader>
                <SheetTitle>Filters</SheetTitle>
              </SheetHeader>
              <div className="mt-4">
                <LeadFilters
                  filters={filters}
                  onFilterChange={(f) => {
                    setFilters(f);
                    if ("borough" in f) setBorough(String(f.borough ?? ""));
                    if ("pipeline_stage" in f) setStage(String(f.pipeline_stage ?? ""));
                  }}
                />
              </div>
            </SheetContent>
          </Sheet>

          <Select value={stage} onValueChange={(v) => setStage(v ?? "")}>
            <SelectTrigger className="w-[120px] sm:w-[150px]">
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

      {/* Borough Tabs — scrollable on mobile */}
      <Tabs value={borough} onValueChange={setBorough}>
        <div className="-mx-4 overflow-x-auto px-4 md:mx-0 md:px-0">
          <TabsList className="inline-flex w-max justify-start md:w-full">
            {BOROUGHS.map((b) => (
              <TabsTrigger key={b.value} value={b.value} className="gap-1 whitespace-nowrap text-xs sm:gap-2 sm:text-sm">
                {b.label}
                {!isLoading && (
                  <Badge variant="secondary" className="ml-0.5 h-5 min-w-[20px] px-1 text-xs sm:ml-1 sm:px-1.5">
                    {b.value === ""
                      ? data?.total ?? 0
                      : boroughCounts[b.value] ?? 0}
                  </Badge>
                )}
              </TabsTrigger>
            ))}
          </TabsList>
        </div>

        {/* Single content area for all tabs */}
        {BOROUGHS.map((b) => (
          <TabsContent key={b.value} value={b.value}>
            {isLoading ? (
              <div className="grid gap-4 pt-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
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
              <div className="grid gap-4 pt-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
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
