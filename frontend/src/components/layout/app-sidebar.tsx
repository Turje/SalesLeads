import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Users,
  Mail,
  Download,
} from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";

const navItems = [
  { title: "Leads", icon: Users, to: "/" },
  { title: "Pipeline", icon: LayoutDashboard, to: "/pipeline" },
  { title: "Email Drafter", icon: Mail, to: "/email" },
  { title: "Export", icon: Download, to: "/export" },
];

export function AppSidebar() {
  return (
    <Sidebar>
      <SidebarHeader className="border-b border-sidebar-border px-4 py-4">
        <div className="flex flex-col gap-0.5">
          <span className="text-base font-semibold text-sidebar-foreground">
            SalesLeads
          </span>
          <span className="text-xs text-sidebar-foreground/60">
            CRE Lead Intelligence
          </span>
        </div>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Navigation</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {navItems.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <NavLink to={item.to}>
                    {({ isActive }) => (
                      <SidebarMenuButton
                        isActive={isActive}
                        tooltip={item.title}
                      >
                        <item.icon className="size-4" />
                        <span>{item.title}</span>
                      </SidebarMenuButton>
                    )}
                  </NavLink>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter className="border-t border-sidebar-border px-4 py-3">
        <span className="text-xs text-sidebar-foreground/40">
          SalesLeads v1.0
        </span>
      </SidebarFooter>
    </Sidebar>
  );
}
