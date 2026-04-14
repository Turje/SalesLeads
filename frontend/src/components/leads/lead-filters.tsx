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

const BOROUGH_NEIGHBORHOODS: Record<string, string[]> = {
  Manhattan: [
    "Battery Park City", "Chelsea", "Financial District", "Flatiron",
    "Hudson Yards", "Midtown", "Midtown East", "Midtown South",
    "Midtown West", "Penn District", "SoHo", "Tribeca",
  ],
  Brooklyn: [
    "Brooklyn Heights", "Downtown Brooklyn", "DUMBO",
    "East Williamsburg", "Navy Yard", "Park Slope",
    "Sunset Park", "Williamsburg",
  ],
  Queens: [
    "Astoria", "Flushing", "Jamaica", "Long Island City", "Rego Park",
  ],
  Bronx: [
    "Fordham", "Foxhurst", "Grand Concourse", "Hunts Point",
    "Mott Haven", "Pelham Bay", "Port Morris", "South Bronx", "Soundview",
  ],
  "Staten Island": [
    "New Dorp", "St. George", "Stapleton", "Tompkinsville",
  ],
};

const COMPANY_TYPES = [
  { value: "CRE_OPERATOR", label: "CRE Operator" },
  { value: "COWORKING", label: "Coworking" },
  { value: "MULTI_TENANT", label: "Multi Tenant" },
  { value: "OTHER", label: "Other" },
];
const STAGES = ["NEW", "APPROVED", "CONTACTED", "MEETING", "PROPOSAL", "CONTRACT_SIGNED", "CLOSED", "DISAPPROVED"];

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
          onValueChange={(v) => onFilterChange({ ...filters, borough: v ?? "", neighborhood: "" })}
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
        <Select
          value={String(filters.neighborhood ?? "")}
          onValueChange={(v) => update("neighborhood", v ?? "")}
          disabled={!filters.borough}
        >
          <SelectTrigger className="w-full" id="neighborhood-filter">
            <SelectValue placeholder={filters.borough ? "Select neighborhood" : "Select a borough first"} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="">All neighborhoods</SelectItem>
            {(BOROUGH_NEIGHBORHOODS[String(filters.borough)] ?? []).map((hood) => (
              <SelectItem key={hood} value={hood}>
                {hood}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
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
