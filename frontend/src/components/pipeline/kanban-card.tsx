import { useNavigate } from "react-router-dom";
import { Draggable } from "@hello-pangea/dnd";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Building2, MapPin, User, Mail, Phone } from "lucide-react";
import type { Lead } from "@/lib/types";

interface KanbanCardProps {
  lead: Lead;
  index: number;
}

export function KanbanCard({ lead, index }: KanbanCardProps) {
  const navigate = useNavigate();

  const handleClick = (e: React.MouseEvent) => {
    // Don't navigate if the user is dragging
    if ((e.target as HTMLElement).closest("[data-rbd-drag-handle-draggable-id]")) {
      // Allow click-through only if it's a real click (not drag end)
    }
    navigate(`/leads/${lead.id}`);
  };

  return (
    <Draggable draggableId={String(lead.id)} index={index}>
      {(provided, snapshot) => (
        <div
          ref={provided.innerRef}
          {...provided.draggableProps}
          {...provided.dragHandleProps}
          className="mb-2"
        >
          <Card
            size="sm"
            className={`cursor-pointer transition-all hover:border-primary/40 ${
              snapshot.isDragging
                ? "ring-2 ring-primary/50 shadow-lg"
                : "hover:shadow-md"
            }`}
            onClick={handleClick}
          >
            <CardContent className="space-y-2">
              <p className="font-semibold leading-tight truncate text-sm">
                {lead.company_name}
              </p>

              {lead.contact_name && (
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <User className="size-3 shrink-0" />
                  <span className="truncate">
                    {lead.contact_name}
                    {lead.contact_title ? ` — ${lead.contact_title}` : ""}
                  </span>
                </div>
              )}

              {(lead.email || lead.phone) && (
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  {lead.email && (
                    <div className="flex items-center gap-1 truncate">
                      <Mail className="size-3 shrink-0" />
                      <span className="truncate">{lead.email}</span>
                    </div>
                  )}
                  {lead.phone && !lead.email && (
                    <div className="flex items-center gap-1">
                      <Phone className="size-3 shrink-0" />
                      <span>{lead.phone}</span>
                    </div>
                  )}
                </div>
              )}

              {(lead.borough || lead.neighborhood) && (
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <MapPin className="size-3 shrink-0" />
                  <span className="truncate">
                    {[lead.neighborhood, lead.borough]
                      .filter(Boolean)
                      .join(", ")}
                  </span>
                </div>
              )}

              {lead.building_type && (
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <Building2 className="size-3 shrink-0" />
                  <span className="truncate">
                    {lead.building_type}
                    {lead.sqft ? ` · ${(lead.sqft / 1000).toFixed(0)}k sqft` : ""}
                  </span>
                </div>
              )}

              {lead.sources.length > 0 && (
                <div className="flex flex-wrap gap-1 pt-0.5">
                  {lead.sources.slice(0, 2).map((source) => (
                    <Badge
                      key={source}
                      variant="secondary"
                      className="text-[10px] px-1.5 py-0"
                    >
                      {source}
                    </Badge>
                  ))}
                  {lead.sources.length > 2 && (
                    <Badge
                      variant="secondary"
                      className="text-[10px] px-1.5 py-0"
                    >
                      +{lead.sources.length - 2}
                    </Badge>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </Draggable>
  );
}
