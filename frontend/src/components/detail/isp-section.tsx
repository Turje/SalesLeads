import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Wifi } from "lucide-react";
import type { Lead } from "@/lib/types";

interface ISPSectionProps {
  lead: Lead;
}

export function ISPSection({ lead }: ISPSectionProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Wifi className="size-4 text-muted-foreground" />
          Internet Service Providers
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1">
            <span className="text-xs text-muted-foreground">
              Current Building ISP
            </span>
            {lead.building_isp ? (
              <Badge variant="default" className="w-fit">
                {lead.building_isp}
              </Badge>
            ) : (
              <span className="text-sm text-muted-foreground">Unknown</span>
            )}
          </div>

          <div className="flex flex-col gap-1.5">
            <span className="text-xs text-muted-foreground">
              Available ISPs
            </span>
            {lead.available_isps.length > 0 ? (
              <div className="flex flex-wrap gap-1.5">
                {lead.available_isps.map((isp) => (
                  <Badge key={isp} variant="outline">
                    {isp}
                  </Badge>
                ))}
              </div>
            ) : (
              <span className="text-sm text-muted-foreground">
                No data available
              </span>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
