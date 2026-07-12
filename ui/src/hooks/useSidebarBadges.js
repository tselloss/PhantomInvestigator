import { useEffect, useState } from "react";

const POLL_MS = 15000;

// Live counts shown as small badges on sidebar nav links -- keyed by the
// NAV_LINKS "to" path they attach to. "warn" surfaces something that needs
// operator action; "muted" is purely informational. Zero-count entries are
// omitted entirely so an empty inbox doesn't clutter the sidebar.
export default function useSidebarBadges() {
  const [badges, setBadges] = useState({});

  useEffect(() => {
    let cancelled = false;

    async function refresh() {
      try {
        const [investigationsRes, clientsRes] = await Promise.all([
          fetch("/api/investigations?status=awaiting_approval&limit=100"),
          fetch("/api/clients"),
        ]);
        if (cancelled) return;
        const next = {};
        if (investigationsRes.ok) {
          const awaiting = await investigationsRes.json();
          if (awaiting.length > 0) {
            next["/investigations"] = { count: awaiting.length, variant: "warn" };
          }
        }
        if (clientsRes.ok) {
          const activeClients = await clientsRes.json();
          if (activeClients.length > 0) {
            next["/clients"] = { count: activeClients.length, variant: "muted" };
          }
        }
        if (!cancelled) setBadges(next);
      } catch {
        // Sidebar badges are decorative -- a transient network hiccup
        // shouldn't surface an error anywhere, just skip this refresh.
      }
    }

    refresh();
    const id = setInterval(refresh, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  return badges;
}
