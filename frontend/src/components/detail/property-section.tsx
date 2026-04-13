import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Building2, MapPin, Calendar, Layers } from "lucide-react";
import type { Lead } from "@/lib/types";

interface PropertySectionProps {
  lead: Lead;
}

function formatNumber(n: number | null): string {
  if (n == null) return "N/A";
  return n.toLocaleString();
}

export function PropertySection({ lead }: PropertySectionProps) {
  const items = [
    {
      icon: MapPin,
      label: "Address",
      value: lead.address,
    },
    {
      icon: Building2,
      label: "Building Type",
      value: lead.building_type,
    },
    {
      icon: Building2,
      label: "Square Footage",
      value: lead.sqft ? `${formatNumber(lead.sqft)} sqft` : "N/A",
    },
    {
      icon: Building2,
      label: "Tenants",
      value: lead.num_tenants != null ? String(lead.num_tenants) : "N/A",
    },
    {
      icon: MapPin,
      label: "Borough",
      value: lead.borough,
    },
    {
      icon: MapPin,
      label: "Neighborhood",
      value: lead.neighborhood,
    },
    {
      icon: Calendar,
      label: "Year Built",
      value: lead.year_built != null ? String(lead.year_built) : "N/A",
    },
    {
      icon: Layers,
      label: "Floors",
      value: lead.floors != null ? String(lead.floors) : "N/A",
    },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Building2 className="size-4 text-muted-foreground" />
          Property Details
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-4">
          {items.map((item) => (
            <div key={item.label} className="flex flex-col gap-0.5">
              <div className="flex items-center gap-1.5">
                <item.icon className="size-3 text-muted-foreground" />
                <span className="text-xs text-muted-foreground">
                  {item.label}
                </span>
              </div>
              <span className="text-sm font-medium text-foreground">
                {item.value}
              </span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
