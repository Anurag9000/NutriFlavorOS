import {
  BarChart3,
  Beaker,
  Clock3,
  Home,
  LayoutDashboard,
  ListChecks,
  LogOut,
  Settings,
  UtensilsCrossed,
} from "lucide-react";
import { NavLink } from "@/components/NavLink";
import { useAuth } from "@/contexts/AuthContext";
import { useNavigate } from "react-router-dom";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";

const navItems = [
  { title: "Dashboard", url: "/dashboard", icon: LayoutDashboard },
  { title: "Meal Planner", url: "/meals", icon: UtensilsCrossed },
  { title: "Analytics", url: "/analytics", icon: BarChart3 },
  { title: "Household & Pantry", url: "/household", icon: Home },
  { title: "Preparation Editor", url: "/preparation", icon: Clock3 },
  {
    title: "Reviewed Prep Pipeline",
    url: "/preparation/pipeline",
    icon: ListChecks,
  },
  { title: "Research Registry", url: "/research", icon: Beaker },
  { title: "Settings", url: "/settings", icon: Settings },
];

export function AppSidebar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const { state } = useSidebar();
  const collapsed = state === "collapsed";
  const handleLogout = () => {
    logout();
    navigate("/");
  };
  return (
    <Sidebar
      collapsible="icon"
      className="bg-sidebar/60 backdrop-blur-xl border-r border-white/10 shadow-xl"
      aria-label="Primary navigation"
    >
      <div className="p-4 border-b border-sidebar-border">
        <div className="flex items-center gap-2">
          <div
            className="h-8 w-8 rounded-lg bg-primary flex items-center justify-center text-primary-foreground font-bold text-sm shrink-0"
            aria-hidden="true"
          >
            N
          </div>
          {!collapsed && (
            <span className="font-semibold text-sm text-sidebar-foreground">
              NutriFlavorOS
            </span>
          )}
        </div>
      </div>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              {navItems.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <SidebarMenuButton asChild tooltip={item.title}>
                    <NavLink
                      to={item.url}
                      end={item.url === "/dashboard" || item.url === "/preparation"}
                      className="hover:bg-sidebar-accent focus-visible:ring-2 focus-visible:ring-ring"
                      activeClassName="bg-sidebar-accent text-primary font-medium"
                    >
                      <item.icon className="h-4 w-4" aria-hidden="true" />
                      <span>{item.title}</span>
                    </NavLink>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter>
        <div className="flex items-center gap-3 p-2">
          <Avatar className="h-8 w-8 shrink-0">
            <AvatarFallback className="bg-primary/20 text-primary text-xs">
              {user?.name?.charAt(0) ?? "U"}
            </AvatarFallback>
          </Avatar>
          {!collapsed && (
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate text-sidebar-foreground">
                {user?.name}
              </p>
              <p className="text-xs truncate text-muted-foreground">
                {user?.email}
              </p>
              {user && !user.profileComplete && (
                <p className="text-xs text-amber-600 dark:text-amber-400">
                  Profile incomplete
                </p>
              )}
            </div>
          )}
          {!collapsed && (
            <button
              type="button"
              onClick={handleLogout}
              className="rounded-md p-2 text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              aria-label="Sign out"
            >
              <LogOut className="h-4 w-4" aria-hidden="true" />
            </button>
          )}
        </div>
      </SidebarFooter>
    </Sidebar>
  );
}
