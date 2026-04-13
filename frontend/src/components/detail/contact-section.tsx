import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { User, Mail, Phone, ExternalLink, Globe } from "lucide-react";
import type { Lead } from "@/lib/types";

interface ContactSectionProps {
  lead: Lead;
}

export function ContactSection({ lead }: ContactSectionProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <User className="size-4 text-muted-foreground" />
          Contact Information
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-0.5">
            <span className="text-xs text-muted-foreground">Name</span>
            <span className="font-medium text-foreground">
              {lead.contact_name}
            </span>
          </div>

          {lead.contact_title && (
            <div className="flex flex-col gap-0.5">
              <span className="text-xs text-muted-foreground">Title</span>
              <span className="text-foreground">{lead.contact_title}</span>
            </div>
          )}

          {lead.email && (
            <div className="flex items-center gap-2">
              <Mail className="size-4 text-muted-foreground" />
              <a
                href={`mailto:${lead.email}`}
                className="text-primary hover:underline"
              >
                {lead.email}
              </a>
            </div>
          )}

          {lead.phone && (
            <div className="flex items-center gap-2">
              <Phone className="size-4 text-muted-foreground" />
              <a
                href={`tel:${lead.phone}`}
                className="text-primary hover:underline"
              >
                {lead.phone}
              </a>
            </div>
          )}

          {lead.linkedin_url && (
            <div className="flex items-center gap-2">
              <ExternalLink className="size-4 text-muted-foreground" />
              <a
                href={lead.linkedin_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary hover:underline"
              >
                LinkedIn Profile
              </a>
            </div>
          )}

          {lead.website && (
            <div className="flex items-center gap-2">
              <Globe className="size-4 text-muted-foreground" />
              <a
                href={lead.website}
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary hover:underline"
              >
                {lead.website}
              </a>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
