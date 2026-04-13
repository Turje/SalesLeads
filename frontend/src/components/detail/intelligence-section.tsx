import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  BrainCircuit,
  Monitor,
  Newspaper,
  Link as LinkIcon,
} from "lucide-react";
import type { Lead } from "@/lib/types";

interface IntelligenceSectionProps {
  lead: Lead;
}

export function IntelligenceSection({ lead }: IntelligenceSectionProps) {
  const socialEntries = Object.entries(lead.social_links);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <BrainCircuit className="size-4 text-muted-foreground" />
          Intelligence
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex flex-col gap-5">
          {/* Current IT Provider */}
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-2">
              <Monitor className="size-3.5 text-muted-foreground" />
              <span className="text-xs font-medium text-muted-foreground">
                Current IT Provider
              </span>
            </div>
            <span className="text-sm text-foreground">
              {lead.current_it_provider ?? "Unknown"}
            </span>
          </div>

          <Separator />

          {/* Tech Signals */}
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2">
              <BrainCircuit className="size-3.5 text-muted-foreground" />
              <span className="text-xs font-medium text-muted-foreground">
                Tech Signals
              </span>
            </div>
            {lead.tech_signals.length > 0 ? (
              <div className="flex flex-wrap gap-1.5">
                {lead.tech_signals.map((signal) => (
                  <Badge key={signal} variant="secondary">
                    {signal}
                  </Badge>
                ))}
              </div>
            ) : (
              <span className="text-sm text-muted-foreground">
                No tech signals detected
              </span>
            )}
          </div>

          <Separator />

          {/* Recent News */}
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2">
              <Newspaper className="size-3.5 text-muted-foreground" />
              <span className="text-xs font-medium text-muted-foreground">
                Recent News
              </span>
            </div>
            {lead.recent_news.length > 0 ? (
              <ul className="flex flex-col gap-1.5">
                {lead.recent_news.map((news, i) => (
                  <li
                    key={i}
                    className="text-sm text-foreground before:mr-2 before:content-['•']"
                  >
                    {news}
                  </li>
                ))}
              </ul>
            ) : (
              <span className="text-sm text-muted-foreground">
                No recent news
              </span>
            )}
          </div>

          {socialEntries.length > 0 && (
            <>
              <Separator />

              {/* Social Links */}
              <div className="flex flex-col gap-2">
                <div className="flex items-center gap-2">
                  <LinkIcon className="size-3.5 text-muted-foreground" />
                  <span className="text-xs font-medium text-muted-foreground">
                    Social Links
                  </span>
                </div>
                <div className="flex flex-wrap gap-2">
                  {socialEntries.map(([platform, url]) => (
                    <a
                      key={platform}
                      href={url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1 text-sm text-primary hover:bg-muted"
                    >
                      <LinkIcon className="size-3" />
                      {platform}
                    </a>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
