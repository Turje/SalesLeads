import { Droppable } from "@hello-pangea/dnd";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { KanbanCard } from "./kanban-card";
import type { Lead } from "@/lib/types";

interface KanbanColumnProps {
  stage: string;
  leads: Lead[];
  label: string;
  color: string;
  icon?: React.ElementType;
  description: string;
}

export function KanbanColumn({
  stage,
  leads,
  label,
  color,
  icon: Icon,
  description,
}: KanbanColumnProps) {
  return (
    <div className="flex w-80 shrink-0 flex-col rounded-lg bg-muted/50 border border-border">
      <div className="flex items-center gap-2 px-3 py-3 border-b border-border">
        {Icon && <Icon className={`size-4 ${color}`} />}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className={`text-sm font-semibold ${color}`}>{label}</h3>
            <Badge variant="secondary" className="text-xs">
              {leads.length}
            </Badge>
          </div>
          <p className="text-[11px] text-muted-foreground truncate">
            {description}
          </p>
        </div>
      </div>
      <Droppable droppableId={stage}>
        {(provided, snapshot) => (
          <div
            ref={provided.innerRef}
            {...provided.droppableProps}
            className={`min-h-[120px] flex-1 p-2 transition-colors ${
              snapshot.isDraggingOver ? "bg-accent/30" : ""
            }`}
          >
            <ScrollArea className="h-[calc(100vh-320px)]">
              {leads.length === 0 && !snapshot.isDraggingOver && (
                <div className="flex items-center justify-center py-8 text-xs text-muted-foreground/60">
                  Drop leads here
                </div>
              )}
              {leads.map((lead, index) => (
                <KanbanCard key={lead.id} lead={lead} index={index} />
              ))}
              {provided.placeholder}
            </ScrollArea>
          </div>
        )}
      </Droppable>
    </div>
  );
}
