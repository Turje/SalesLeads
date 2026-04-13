import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Thermometer,
  ArrowUpDown,
  Shield,
  Cpu,
  Network,
  Wrench,
} from "lucide-react";
import type { Lead } from "@/lib/types";
import type { LucideIcon } from "lucide-react";

interface EquipmentSectionProps {
  lead: Lead;
}

const EQUIPMENT_CONFIG: Record<
  string,
  { label: string; icon: LucideIcon }
> = {
  hvac: { label: "HVAC", icon: Thermometer },
  elevator: { label: "Elevator", icon: ArrowUpDown },
  security: { label: "Security", icon: Shield },
  bms: { label: "BMS", icon: Cpu },
  network_infrastructure: { label: "Network Infrastructure", icon: Network },
};

export function EquipmentSection({ lead }: EquipmentSectionProps) {
  const entries = Object.entries(lead.equipment);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Wrench className="size-4 text-muted-foreground" />
          Building Equipment
        </CardTitle>
      </CardHeader>
      <CardContent>
        {entries.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No equipment data available.
          </p>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            {entries.map(([key, value]) => {
              const config = EQUIPMENT_CONFIG[key];
              const Icon = config?.icon ?? Wrench;
              const label = config?.label ?? key.replace(/_/g, " ");

              return (
                <div
                  key={key}
                  className="flex items-start gap-3 rounded-lg border border-border bg-muted/30 p-3"
                >
                  <Icon className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
                  <div className="flex flex-col gap-0.5">
                    <span className="text-xs font-medium text-muted-foreground capitalize">
                      {label}
                    </span>
                    <span className="text-sm text-foreground">{value}</span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
