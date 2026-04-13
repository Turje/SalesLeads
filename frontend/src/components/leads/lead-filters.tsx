import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { RotateCcw } from "lucide-react";

interface LeadFiltersProps {
  filters: Record<string, string | number>;
  onFilterChange: (filters: Record<string, string | number>) => void;
}

const BOROUGHS = ["Manhattan", "Brooklyn", "Queens", "Bronx", "Staten Island"];
const COMPANY_TYPES = [
  { value: "CRE_OPERATOR", label: "CRE Operator" },
  { value: "COWORKING", label: "Coworking" },
  { value: "MULTI_TENANT", label: "Multi Tenant" },
  { value: "OTHER", label: "Other" },
];
const STAGES = ["NEW", "APPROVED", "CONTACTED", "MEETING", "PROPOSAL", "CLOSED", "DISAPPROVED"];

export function LeadFilters({ filters, onFilterChange }: LeadFiltersProps) {
  const update = (key: string, value: string | number) => {
    onFilterChange({ ...filters, [key]: value });
  };

  const reset = () => {
    onFilterChange({});
  };

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-foreground">Filters</h3>
        <Button variant="ghost" size="xs" onClick={reset}>
          <RotateCcw className="size-3" />
          Reset
        </Button>
      </div>

      <Separator />

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="borough-filter">Borough</Label>
        <Select
          value={String(filters.borough ?? "")}
          onValueChange={(v) => update("borough", v ?? "")}
        >
          <SelectTrigger className="w-full" id="borough-filter">
            <SelectValue placeholder="All boroughs" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="">All</SelectItem>
            {BOROUGHS.map((b) => (
              <SelectItem key={b} value={b}>
                {b}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="neighborhood-filter">Neighborhood</Label>
        <Input
          id="neighborhood-filter"
          placeholder="Filter by neighborhood..."
          value={String(filters.neighborhood ?? "")}
          onChange={(e) => update("neighborhood", e.target.value)}
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="company-type-filter">Company Type</Label>
        <Select
          value={String(filters.company_type ?? "")}
          onValueChange={(v) => update("company_type", v ?? "")}
        >
          <SelectTrigger className="w-full" id="company-type-filter">
            <SelectValue placeholder="All types" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="">All</SelectItem>
            {COMPANY_TYPES.map((t) => (
              <SelectItem key={t.value} value={t.value}>
                {t.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="stage-filter">Pipeline Stage</Label>
        <Select
          value={String(filters.pipeline_stage ?? "")}
          onValueChange={(v) => update("pipeline_stage", v ?? "")}
        >
          <SelectTrigger className="w-full" id="stage-filter">
            <SelectValue placeholder="All stages" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="">All</SelectItem>
            {STAGES.map((s) => (
              <SelectItem key={s} value={s}>
                {s.charAt(0) + s.slice(1).toLowerCase()}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="source-filter">Source</Label>
        <Input
          id="source-filter"
          placeholder="Filter by source..."
          value={String(filters.source ?? "")}
          onChange={(e) => update("source", e.target.value)}
        />
      </div>
    </div>
  );
}
