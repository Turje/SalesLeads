import { Badge } from "@/components/ui/badge";

export function ScoreBadge({ score }: { score: number }) {
  const color =
    score >= 80
      ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/30"
      : score >= 60
        ? "bg-amber-500/20 text-amber-400 border-amber-500/30"
        : "bg-red-500/20 text-red-400 border-red-500/30";
  return (
    <Badge variant="outline" className={color}>
      {score}
    </Badge>
  );
}
