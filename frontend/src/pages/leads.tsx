import { useState } from "react";
import { useLeads } from "@/hooks/use-leads";
import { LeadFilters } from "@/components/leads/lead-filters";
import { LeadTable } from "@/components/leads/lead-table";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { SlidersHorizontal } from "lucide-react";

export default function LeadsPage() {
  const [filters, setFilters] = useState<Record<string, string | number>>({});
  const [page, setPage] = useState(1);
  const pageSize = 50;

  const params = { ...filters, page, page_size: pageSize };
  const { data, isLoading } = useLeads(params);

  // Count NEW leads to show in header
  const newCount = data?.items?.filter((l) => l.pipeline_stage === "NEW").length ?? 0;

  const handleFilterChange = (newFilters: Record<string, string | number>) => {
    setFilters(newFilters);
    setPage(1);
  };

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Leads</h1>
          <p className="text-sm text-muted-foreground">
            {isLoading
              ? "Loading..."
              : `${data?.total ?? 0} leads found`}
          </p>
        </div>

        <div className="flex items-center gap-3">
          {!isLoading && newCount > 0 && (
            <Badge variant="secondary" className="px-3 py-1 text-sm">
              {newCount} awaiting review
            </Badge>
          )}

          {/* Mobile filter trigger */}
          <div className="lg:hidden">
            <Sheet>
              <SheetTrigger
                render={
                  <Button variant="outline" size="sm">
                    <SlidersHorizontal className="size-4" />
                    Filters
                  </Button>
                }
              />
              <SheetContent side="left">
                <SheetHeader>
                  <SheetTitle>Filter Leads</SheetTitle>
                </SheetHeader>
                <div className="p-4">
                  <LeadFilters
                    filters={filters}
                    onFilterChange={handleFilterChange}
                  />
                </div>
              </SheetContent>
            </Sheet>
          </div>
        </div>
      </div>

      <div className="flex gap-6">
        {/* Desktop sidebar filters */}
        <aside className="hidden w-[250px] shrink-0 lg:block">
          <div className="rounded-lg border border-border bg-card p-4">
            <LeadFilters
              filters={filters}
              onFilterChange={handleFilterChange}
            />
          </div>
        </aside>

        {/* Table area */}
        <div className="min-w-0 flex-1">
          {isLoading ? (
            <div className="flex flex-col gap-3">
              <Skeleton className="h-10 w-full" />
              {Array.from({ length: 8 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : (
            <LeadTable
              data={data?.items ?? []}
              total={data?.total ?? 0}
              page={data?.page ?? page}
              pageSize={data?.page_size ?? pageSize}
              onPageChange={setPage}
            />
          )}
        </div>
      </div>
    </div>
  );
}
