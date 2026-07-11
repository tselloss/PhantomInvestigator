// Shared display metadata for the integration keys returned by
// /api/settings/integrations. Keeps Dashboard's status tiles and the
// Integrations settings page from drifting into inconsistent labels --
// and makes near-namesakes like "azure" (Azure Monitor, metrics/logs) vs
// "azure_devops" (Azure Boards, tickets) legible at a glance instead of
// reading as duplicates.
const INTEGRATION_META = {
  jira: { label: "Jira", role: "Tickets & postmortems" },
  github: { label: "GitHub", role: "Deploys & CI logs" },
  azure: { label: "Azure", role: "Metrics & logs · Azure Monitor" },
  aws: { label: "AWS", role: "Metrics & logs · CloudWatch" },
  prometheus: { label: "Prometheus", role: "Metrics" },
  loki: { label: "Loki", role: "Logs" },
  azure_devops: { label: "Azure DevOps", role: "Tickets & work items · Azure Boards" },
  zendesk: { label: "Zendesk", role: "Customer support tickets" },
};

export function integrationLabel(name) {
  return INTEGRATION_META[name]?.label || name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function integrationRole(name) {
  return INTEGRATION_META[name]?.role || "";
}
