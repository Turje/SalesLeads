import { useState } from "react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { useUpdateNotes } from "@/hooks/use-leads";
import { toast } from "sonner";
import { StickyNote, Save } from "lucide-react";

interface NotesSectionProps {
  leadId: number;
  notes: string;
}

export function NotesSection({ leadId, notes }: NotesSectionProps) {
  const [value, setValue] = useState(notes);
  const updateNotes = useUpdateNotes();

  const handleSave = () => {
    updateNotes.mutate(
      { id: leadId, notes: value },
      {
        onSuccess: () => {
          toast.success("Notes saved successfully");
        },
        onError: () => {
          toast.error("Failed to save notes");
        },
      }
    );
  };

  const isDirty = value !== notes;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <StickyNote className="size-4 text-muted-foreground" />
          Qualification Notes
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex flex-col gap-3">
          <Textarea
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="Add notes about this lead..."
            className="min-h-[150px]"
          />
          <div className="flex justify-end">
            <Button
              onClick={handleSave}
              disabled={!isDirty || updateNotes.isPending}
            >
              <Save className="size-4" />
              {updateNotes.isPending ? "Saving..." : "Save Notes"}
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
