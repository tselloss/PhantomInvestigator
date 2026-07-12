import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import Icon from "../components/Icon";
import Skeleton from "../components/Skeleton";
import { integrationLabel, integrationRole } from "../lib/integrations";
import { useToast } from "../context/ToastContext";

function slugify(name) {
  return name.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
}

export default function Clients() {
  const toast = useToast();
  const navigate = useNavigate();
  const [clients, setClients] = useState(null);
  const [error, setError] = useState(null);
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);

  const [expandedId, setExpandedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [activeTab, setActiveTab] = useState("deployments");
  const [deployLabel, setDeployLabel] = useState("");
  const [deployEnv, setDeployEnv] = useState("production");
  const [deployJira, setDeployJira] = useState("");
  const [deployRepo, setDeployRepo] = useState("");
  const [deployAzureDevOps, setDeployAzureDevOps] = useState("");

  const [editingClientId, setEditingClientId] = useState(null);
  const [editClientName, setEditClientName] = useState("");
  const [editClientNotes, setEditClientNotes] = useState("");
  const [savingClient, setSavingClient] = useState(false);
  const [confirmArchiveClientId, setConfirmArchiveClientId] = useState(null);

  const [expandedDeploymentId, setExpandedDeploymentId] = useState(null);
  const [deploymentDetail, setDeploymentDetail] = useState(null);
  const [bundles, setBundles] = useState([]);
  const [uploading, setUploading] = useState(false);

  const [editingDeploymentId, setEditingDeploymentId] = useState(null);
  const [editDeployLabel, setEditDeployLabel] = useState("");
  const [editDeployEnv, setEditDeployEnv] = useState("production");
  const [editDeployJira, setEditDeployJira] = useState("");
  const [editDeployRepo, setEditDeployRepo] = useState("");
  const [editDeployAzureDevOps, setEditDeployAzureDevOps] = useState("");
  const [editDeployAllowedBranches, setEditDeployAllowedBranches] = useState("");
  const [savingDeployment, setSavingDeployment] = useState(false);
  const [confirmArchiveDeploymentId, setConfirmArchiveDeploymentId] = useState(null);

  const [integrationFieldSchema, setIntegrationFieldSchema] = useState({});
  const [clientIntegrations, setClientIntegrations] = useState([]);
  const [tickets, setTickets] = useState([]);
  const [ticketsLoading, setTicketsLoading] = useState(false);
  const [editingIntegration, setEditingIntegration] = useState(null);
  const [integrationFormValues, setIntegrationFormValues] = useState({});
  const [savingIntegration, setSavingIntegration] = useState(false);
  const [integrationSaveError, setIntegrationSaveError] = useState(null);
  const [testingIntegration, setTestingIntegration] = useState(null);
  const [integrationTestResults, setIntegrationTestResults] = useState({});
  const [confirmClearIntegration, setConfirmClearIntegration] = useState(null);

  async function loadClients() {
    try {
      const res = await fetch("/api/clients");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setClients(await res.json());
    } catch (e) {
      setError(e.message);
    }
  }

  useEffect(() => {
    loadClients();
    fetch("/api/settings/integrations/fields")
      .then((res) => res.json())
      .then(setIntegrationFieldSchema);
  }, []);

  async function createClient() {
    if (!name.trim()) return;
    setCreating(true);
    try {
      const res = await fetch("/api/clients", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, slug: slugify(name) }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        toast.show(detail.detail || `Couldn't add client (HTTP ${res.status})`, { type: "err" });
        return;
      }
      setName("");
      await loadClients();
      toast.show("Client added.", { type: "ok" });
    } catch {
      toast.show("Couldn't add client — check your connection.", { type: "err" });
    } finally {
      setCreating(false);
    }
  }

  async function toggleExpand(clientId) {
    if (expandedId === clientId) {
      setExpandedId(null);
      setDetail(null);
      setClientIntegrations([]);
      setEditingIntegration(null);
      setIntegrationTestResults({});
      setTickets([]);
      return;
    }
    setExpandedId(clientId);
    setActiveTab("deployments");
    setTicketsLoading(true);
    try {
      const [detailRes, integrationsRes, ticketsRes] = await Promise.all([
        fetch(`/api/clients/${clientId}`),
        fetch(`/api/clients/${clientId}/integrations`),
        fetch(`/api/clients/${clientId}/tickets`),
      ]);
      if (!detailRes.ok || !integrationsRes.ok || !ticketsRes.ok) throw new Error("load failed");
      setDetail(await detailRes.json());
      setClientIntegrations(await integrationsRes.json());
      setTickets(await ticketsRes.json());
    } catch {
      toast.show("Couldn't load client details.", { type: "err" });
      setExpandedId(null);
    } finally {
      setTicketsLoading(false);
    }
  }

  async function createDeployment(clientId) {
    if (!deployLabel.trim()) return;
    try {
      const res = await fetch(`/api/clients/${clientId}/deployments`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          label: deployLabel,
          environment: deployEnv,
          jira_project_key: deployJira || null,
          github_repo: deployRepo || null,
          azure_devops_project: deployAzureDevOps || null,
        }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        toast.show(detail.detail || `Couldn't add deployment (HTTP ${res.status})`, { type: "err" });
        return;
      }
      setDeployLabel("");
      setDeployJira("");
      setDeployRepo("");
      setDeployAzureDevOps("");
      const detailRes = await fetch(`/api/clients/${clientId}`);
      if (detailRes.ok) setDetail(await detailRes.json());
      toast.show("Deployment added.", { type: "ok" });
    } catch {
      toast.show("Couldn't add deployment — check your connection.", { type: "err" });
    }
  }

  function startEditClient(c) {
    setEditingClientId(c.id);
    setEditClientName(c.name);
    setEditClientNotes(c.notes || "");
  }

  async function saveClient(clientId) {
    setSavingClient(true);
    try {
      const res = await fetch(`/api/clients/${clientId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: editClientName, notes: editClientNotes || null }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        toast.show(detail.detail || `Couldn't save client (HTTP ${res.status})`, { type: "err" });
        return;
      }
      setEditingClientId(null);
      await loadClients();
      const detailRes = await fetch(`/api/clients/${clientId}`);
      if (detailRes.ok) setDetail(await detailRes.json());
      toast.show("Client saved.", { type: "ok" });
    } catch {
      toast.show("Couldn't save client — check your connection.", { type: "err" });
    } finally {
      setSavingClient(false);
    }
  }

  async function archiveClient(clientId) {
    try {
      const res = await fetch(`/api/clients/${clientId}`, { method: "DELETE" });
      if (!res.ok) {
        toast.show(`Couldn't archive client (HTTP ${res.status})`, { type: "err" });
        return;
      }
      setConfirmArchiveClientId(null);
      if (expandedId === clientId) {
        setExpandedId(null);
        setDetail(null);
      }
      await loadClients();
      toast.show("Client archived.", { type: "ok" });
    } catch {
      toast.show("Couldn't archive client — check your connection.", { type: "err" });
    }
  }

  function startEditIntegration(name) {
    setEditingIntegration(name);
    setIntegrationSaveError(null);
    const blank = {};
    (integrationFieldSchema[name] || []).forEach((f) => (blank[f.key] = ""));
    setIntegrationFormValues(blank);
  }

  function cancelEditIntegration() {
    setEditingIntegration(null);
    setIntegrationSaveError(null);
  }

  async function saveIntegration(clientId, name) {
    setSavingIntegration(true);
    setIntegrationSaveError(null);
    try {
      const res = await fetch(`/api/clients/${clientId}/integrations/${name}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(integrationFormValues),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        setIntegrationSaveError(detail.detail || `HTTP ${res.status}`);
        return;
      }
      setEditingIntegration(null);
      const listRes = await fetch(`/api/clients/${clientId}/integrations`);
      setClientIntegrations(await listRes.json());
      toast.show(`${integrationLabel(name)} override saved.`, { type: "ok" });
    } catch {
      toast.show("Couldn't save override — check your connection.", { type: "err" });
    } finally {
      setSavingIntegration(false);
    }
  }

  async function clearIntegration(clientId, name) {
    setConfirmClearIntegration(null);
    try {
      const res = await fetch(`/api/clients/${clientId}/integrations/${name}`, { method: "DELETE" });
      if (!res.ok) {
        toast.show(`Couldn't clear override (HTTP ${res.status})`, { type: "err" });
        return;
      }
      const listRes = await fetch(`/api/clients/${clientId}/integrations`);
      if (listRes.ok) setClientIntegrations(await listRes.json());
      toast.show(`${integrationLabel(name)} override cleared.`, { type: "ok" });
    } catch {
      toast.show("Couldn't clear override — check your connection.", { type: "err" });
    }
  }

  async function testIntegration(clientId, name) {
    setTestingIntegration(name);
    try {
      const res = await fetch(`/api/clients/${clientId}/integrations/${name}/test`, { method: "POST" });
      const data = await res.json().catch(() => ({ ok: false, detail: `HTTP ${res.status}` }));
      setIntegrationTestResults((r) => ({ ...r, [name]: data }));
      toast.show(data.detail || (data.ok ? "Connection OK." : "Connection failed."), { type: data.ok ? "ok" : "err" });
    } catch {
      const data = { ok: false, detail: "Connection test failed — check your connection." };
      setIntegrationTestResults((r) => ({ ...r, [name]: data }));
      toast.show(data.detail, { type: "err" });
    } finally {
      setTestingIntegration(null);
    }
  }

  function startEditDeployment(d) {
    setEditingDeploymentId(d.id);
    setEditDeployLabel(d.label);
    setEditDeployEnv(d.environment);
    setEditDeployJira(d.jira_project_key || "");
    setEditDeployRepo(d.github_repo || "");
    setEditDeployAzureDevOps(d.azure_devops_project || "");
    setEditDeployAllowedBranches((d.allowed_base_branches || []).join(", "));
  }

  async function saveDeployment(clientId, deploymentId) {
    setSavingDeployment(true);
    try {
      const allowedBranches = editDeployAllowedBranches
        .split(",")
        .map((b) => b.trim())
        .filter(Boolean);
      const res = await fetch(`/api/clients/${clientId}/deployments/${deploymentId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          label: editDeployLabel,
          environment: editDeployEnv,
          jira_project_key: editDeployJira || null,
          github_repo: editDeployRepo || null,
          azure_devops_project: editDeployAzureDevOps || null,
          allowed_base_branches: allowedBranches.length ? allowedBranches : null,
        }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        toast.show(detail.detail || `Couldn't save deployment (HTTP ${res.status})`, { type: "err" });
        return;
      }
      setEditingDeploymentId(null);
      const [depRes, clientRes] = await Promise.all([
        fetch(`/api/clients/${clientId}/deployments/${deploymentId}`),
        fetch(`/api/clients/${clientId}`),
      ]);
      if (depRes.ok) setDeploymentDetail(await depRes.json());
      if (clientRes.ok) setDetail(await clientRes.json());
      toast.show("Deployment saved.", { type: "ok" });
    } catch {
      toast.show("Couldn't save deployment — check your connection.", { type: "err" });
    } finally {
      setSavingDeployment(false);
    }
  }

  async function archiveDeployment(clientId, deploymentId) {
    try {
      const res = await fetch(`/api/clients/${clientId}/deployments/${deploymentId}`, { method: "DELETE" });
      if (!res.ok) {
        toast.show(`Couldn't archive deployment (HTTP ${res.status})`, { type: "err" });
        return;
      }
      setConfirmArchiveDeploymentId(null);
      if (expandedDeploymentId === deploymentId) {
        setExpandedDeploymentId(null);
        setDeploymentDetail(null);
        setBundles([]);
      }
      const detailRes = await fetch(`/api/clients/${clientId}`);
      if (detailRes.ok) setDetail(await detailRes.json());
      toast.show("Deployment archived.", { type: "ok" });
    } catch {
      toast.show("Couldn't archive deployment — check your connection.", { type: "err" });
    }
  }

  async function toggleDeployment(clientId, deploymentId) {
    if (expandedDeploymentId === deploymentId) {
      setExpandedDeploymentId(null);
      setDeploymentDetail(null);
      setBundles([]);
      return;
    }
    setExpandedDeploymentId(deploymentId);
    try {
      const [depRes, bundlesRes] = await Promise.all([
        fetch(`/api/clients/${clientId}/deployments/${deploymentId}`),
        fetch(`/api/diagnostics/${deploymentId}`),
      ]);
      if (!depRes.ok || !bundlesRes.ok) throw new Error("load failed");
      setDeploymentDetail(await depRes.json());
      setBundles(await bundlesRes.json());
    } catch {
      toast.show("Couldn't load deployment details.", { type: "err" });
      setExpandedDeploymentId(null);
    }
  }

  async function uploadBundle(clientId, deploymentId, form) {
    setUploading(true);
    try {
      const data = new FormData(form);
      data.set("deployment_id", deploymentId);
      if (!data.get("filename")) data.set("filename", "bundle");
      const res = await fetch("/api/diagnostics/upload", { method: "POST", body: data });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        toast.show(detail.detail || `Couldn't upload bundle (HTTP ${res.status})`, { type: "err" });
        return;
      }
      form.reset();
      const [depRes, bundlesRes] = await Promise.all([
        fetch(`/api/clients/${clientId}/deployments/${deploymentId}`),
        fetch(`/api/diagnostics/${deploymentId}`),
      ]);
      if (depRes.ok) setDeploymentDetail(await depRes.json());
      if (bundlesRes.ok) setBundles(await bundlesRes.json());
      toast.show("Bundle uploaded.", { type: "ok" });
    } catch {
      toast.show("Couldn't upload bundle — check your connection.", { type: "err" });
    } finally {
      setUploading(false);
    }
  }

  return (
    <section>
      <h2>Clients</h2>
      <p className="placeholder">
        Each client can run one or more deployments (prod/staging, on-prem or their own cloud). Investigations
        can be linked to a deployment so version/drift history builds up over time instead of resetting per incident.
      </p>

      <div className="row" style={{ marginBottom: 16, alignItems: "flex-end" }}>
        <div className="field grow">
          <label>New client</label>
          <input
            type="text"
            placeholder="e.g. Acme Corp"
            value={name}
            onChange={(e) => setName(e.target.value)}
            disabled={creating}
          />
        </div>
        <button className="primary" disabled={creating || !name.trim()} onClick={createClient}>
          <Icon name="plus" size={14} />
          {creating ? "Adding…" : "Add client"}
        </button>
      </div>

      {error && <div className="alert err">Couldn't load clients: {error}</div>}
      {!error && clients === null && (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <Skeleton height={44} />
          <Skeleton height={44} />
          <Skeleton height={44} />
        </div>
      )}
      {!error && clients?.length === 0 && (
        <div className="empty-state">
          <Icon name="users" size={30} />
          <p>No clients yet — add one above.</p>
        </div>
      )}

      {clients?.map((c) => (
        <div key={c.id} style={{ marginBottom: 8 }}>
          <div className="feed-row" style={{ cursor: "pointer" }} onClick={() => toggleExpand(c.id)}>
            <div className="row" style={{ gap: 8 }}>
              <Icon
                name="chevron"
                size={13}
                className="chevron-icon"
                style={{ transform: expandedId === c.id ? "rotate(90deg)" : "none" }}
              />
              <span>{c.name}</span>
            </div>
            <div className="feed-meta">{c.slug}</div>
          </div>

          {expandedId === c.id && detail && (
            <div className="nested">
              <div className="row" style={{ justifyContent: "space-between", marginBottom: 12, alignItems: "flex-end" }}>
                {editingClientId === c.id ? (
                  <>
                    <div className="field">
                      <label>Name</label>
                      <input value={editClientName} onChange={(e) => setEditClientName(e.target.value)} />
                    </div>
                    <div className="field grow">
                      <label>Notes</label>
                      <input
                        value={editClientNotes}
                        onChange={(e) => setEditClientNotes(e.target.value)}
                        placeholder="Optional"
                      />
                    </div>
                    <button
                      className="primary"
                      disabled={savingClient || !editClientName.trim()}
                      onClick={() => saveClient(c.id)}
                    >
                      <Icon name="check" size={14} />
                      {savingClient ? "Saving…" : "Save"}
                    </button>
                    <button onClick={() => setEditingClientId(null)}>Cancel</button>
                  </>
                ) : (
                  <>
                    <p className="placeholder" style={{ margin: 0 }}>{detail.notes || "No notes."}</p>
                    <div className="row">
                      <button onClick={() => startEditClient(detail)}>Edit</button>
                      {confirmArchiveClientId === c.id ? (
                        <>
                          <span className="placeholder">Archive this client?</span>
                          <button className="danger" onClick={() => archiveClient(c.id)}>Confirm</button>
                          <button onClick={() => setConfirmArchiveClientId(null)}>Cancel</button>
                        </>
                      ) : (
                        <button className="danger" onClick={() => setConfirmArchiveClientId(c.id)}>Archive</button>
                      )}
                    </div>
                  </>
                )}
              </div>

              <div className="subtabs">
                <button
                  className={"subtab" + (activeTab === "deployments" ? " active" : "")}
                  onClick={() => setActiveTab("deployments")}
                >
                  Deployments <span className="count">{detail.deployments.length}</span>
                </button>
                <button
                  className={"subtab" + (activeTab === "tickets" ? " active" : "")}
                  onClick={() => setActiveTab("tickets")}
                >
                  Candidate incidents <span className="count">{ticketsLoading ? "…" : tickets.length}</span>
                </button>
                <button
                  className={"subtab" + (activeTab === "integrations" ? " active" : "")}
                  onClick={() => setActiveTab("integrations")}
                >
                  Integrations{" "}
                  <span className="count">
                    {clientIntegrations.filter((i) => i.configured).length}/{clientIntegrations.length}
                  </span>
                </button>
              </div>

              {activeTab === "deployments" && (
              <div key="deployments" className="tab-panel">
              {detail.deployments.length === 0 && (
                <p className="placeholder" style={{ marginTop: 0 }}>No deployments yet for this client.</p>
              )}
              {detail.deployments.map((d) => (
                <div key={d.id}>
                  <div
                    className="feed-row"
                    style={{ cursor: "pointer" }}
                    onClick={() => toggleDeployment(c.id, d.id)}
                  >
                    <div className="row" style={{ gap: 8 }}>
                      <Icon
                        name="chevron"
                        size={13}
                        className="chevron-icon"
                        style={{ transform: expandedDeploymentId === d.id ? "rotate(90deg)" : "none" }}
                      />
                      <span>{d.label}</span>
                      <span className={"tag" + (d.environment === "production" ? " warn" : "")}>{d.environment}</span>
                      {d.jira_project_key && <span className="tag">Jira {d.jira_project_key}</span>}
                      {d.github_repo && <span className="tag">{d.github_repo}</span>}
                      {d.azure_devops_project && <span className="tag">ADO {d.azure_devops_project}</span>}
                      {d.allowed_base_branches?.length > 0 && (
                        <span className="tag">Auto-fix PRs: {d.allowed_base_branches.join(", ")}</span>
                      )}
                    </div>
                    <div className="feed-meta">id {d.id}</div>
                  </div>

                  {expandedDeploymentId === d.id && deploymentDetail && (
                    <div className="nested">
                      <div className="row" style={{ justifyContent: "space-between", marginBottom: 12, alignItems: "flex-end" }}>
                        {editingDeploymentId === d.id ? (
                          <>
                            <div className="field">
                              <label>Deployment label</label>
                              <input value={editDeployLabel} onChange={(e) => setEditDeployLabel(e.target.value)} />
                            </div>
                            <div className="field">
                              <label>Environment</label>
                              <select value={editDeployEnv} onChange={(e) => setEditDeployEnv(e.target.value)}>
                                <option value="production">production</option>
                                <option value="staging">staging</option>
                              </select>
                            </div>
                            <div className="field">
                              <label>Jira project key</label>
                              <input
                                value={editDeployJira}
                                onChange={(e) => setEditDeployJira(e.target.value)}
                                placeholder="Optional"
                              />
                            </div>
                            <div className="field">
                              <label>GitHub repo</label>
                              <input
                                value={editDeployRepo}
                                onChange={(e) => setEditDeployRepo(e.target.value)}
                                placeholder="Optional"
                              />
                            </div>
                            <div className="field">
                              <label>Azure DevOps org/project</label>
                              <input
                                value={editDeployAzureDevOps}
                                onChange={(e) => setEditDeployAzureDevOps(e.target.value)}
                                placeholder="e.g. contoso/MyProject"
                              />
                            </div>
                            <div className="field">
                              <label>Allowed branches for auto-fix PRs</label>
                              <input
                                value={editDeployAllowedBranches}
                                onChange={(e) => setEditDeployAllowedBranches(e.target.value)}
                                placeholder="e.g. main, staging — blank disables auto-fix PRs"
                              />
                            </div>
                            <button
                              className="primary"
                              disabled={savingDeployment || !editDeployLabel.trim()}
                              onClick={() => saveDeployment(c.id, d.id)}
                            >
                              <Icon name="check" size={14} />
                              {savingDeployment ? "Saving…" : "Save"}
                            </button>
                            <button onClick={() => setEditingDeploymentId(null)}>Cancel</button>
                          </>
                        ) : (
                          <div className="row" style={{ marginLeft: "auto" }}>
                            <button onClick={() => startEditDeployment(d)}>Edit</button>
                            {confirmArchiveDeploymentId === d.id ? (
                              <>
                                <span className="placeholder">Archive this deployment?</span>
                                <button className="danger" onClick={() => archiveDeployment(c.id, d.id)}>Confirm</button>
                                <button onClick={() => setConfirmArchiveDeploymentId(null)}>Cancel</button>
                              </>
                            ) : (
                              <button className="danger" onClick={() => setConfirmArchiveDeploymentId(d.id)}>Archive</button>
                            )}
                          </div>
                        )}
                      </div>

                      <p className="placeholder">
                        Checkin token (for this instance's self-report webhook): <code>{d.checkin_token}</code>
                      </p>

                      {deploymentDetail.latest_snapshot ? (
                        <p className="placeholder">
                          Latest known version: <strong>{deploymentDetail.latest_snapshot.app_version || "unknown"}</strong>
                          {" "}({deploymentDetail.latest_snapshot.source}, {new Date(deploymentDetail.latest_snapshot.reported_at).toLocaleString()})
                        </p>
                      ) : (
                        <p className="placeholder">
                          No version/build info known yet for this deployment — nothing self-reported or uploaded.
                        </p>
                      )}

                      <p className="subheading">Diagnostic bundles</p>
                      {bundles.length === 0 && <p className="placeholder">None uploaded yet.</p>}
                      {bundles.map((b) => (
                        <div className="feed-row" key={b.id}>
                          <div>{b.filename}</div>
                          <div className="feed-meta">{new Date(b.uploaded_at).toLocaleString()}</div>
                        </div>
                      ))}

                      <form
                        className="row"
                        style={{ marginTop: 12, alignItems: "flex-end" }}
                        onSubmit={(e) => {
                          e.preventDefault();
                          uploadBundle(c.id, d.id, e.target);
                        }}
                      >
                        <div className="field">
                          <label>Bundle name</label>
                          <input type="text" name="filename" placeholder="Optional" />
                        </div>
                        <div className="field">
                          <label>Logs</label>
                          <input type="file" name="logs_file" />
                        </div>
                        <div className="field">
                          <label>Config/manifest</label>
                          <input type="file" name="config_file" />
                        </div>
                        <button className="primary" type="submit" disabled={uploading}>
                          <Icon name="plus" size={14} />
                          {uploading ? "Uploading…" : "Upload bundle"}
                        </button>
                      </form>

                      <p className="subheading">Recent investigations</p>
                      {deploymentDetail.recent_investigations.length === 0 && (
                        <p className="placeholder">None yet.</p>
                      )}
                      {deploymentDetail.recent_investigations.map((inv) => (
                        <Link className="feed-row" to={`/investigations/${inv.id}`} key={inv.id}>
                          <div>
                            <span className="feed-source">{inv.source}</span>
                            {inv.source_ref ? ` ${inv.source_ref}` : ""}
                            {" — "}
                            {inv.alert_text.length > 70 ? inv.alert_text.slice(0, 70) + "…" : inv.alert_text}
                          </div>
                          <div className={"feed-status " + inv.status}>{inv.status}</div>
                        </Link>
                      ))}
                    </div>
                  )}
                </div>
              ))}

              <div className="row" style={{ marginTop: 12, alignItems: "flex-end" }}>
                <div className="field">
                  <label>Deployment label</label>
                  <input
                    type="text"
                    placeholder="e.g. prod"
                    value={deployLabel}
                    onChange={(e) => setDeployLabel(e.target.value)}
                  />
                </div>
                <div className="field">
                  <label>Environment</label>
                  <select value={deployEnv} onChange={(e) => setDeployEnv(e.target.value)}>
                    <option value="production">production</option>
                    <option value="staging">staging</option>
                  </select>
                </div>
                <div className="field">
                  <label>Jira project key</label>
                  <input
                    type="text"
                    placeholder="Optional"
                    value={deployJira}
                    onChange={(e) => setDeployJira(e.target.value)}
                  />
                </div>
                <div className="field">
                  <label>GitHub repo</label>
                  <input
                    type="text"
                    placeholder="Optional"
                    value={deployRepo}
                    onChange={(e) => setDeployRepo(e.target.value)}
                  />
                </div>
                <div className="field">
                  <label>Azure DevOps org/project</label>
                  <input
                    type="text"
                    placeholder="e.g. contoso/MyProject"
                    value={deployAzureDevOps}
                    onChange={(e) => setDeployAzureDevOps(e.target.value)}
                  />
                </div>
                <button className="primary" disabled={!deployLabel.trim()} onClick={() => createDeployment(c.id)}>
                  <Icon name="plus" size={14} />
                  Add deployment
                </button>
              </div>
              </div>
              )}

              {activeTab === "tickets" && (
              <div key="tickets" className="tab-panel">
              <p className="placeholder" style={{ marginTop: 0 }}>
                Still-open items from this client's Jira, Azure DevOps, and Zendesk — whichever are configured under
                the Integrations tab, using this client's own override or the shared global default. Anything closed,
                done, resolved, or solved is left out; this is a queue of what might still need investigating, not a
                full ticket history (Jira/Azure DevOps/Zendesk already show that natively).
              </p>
              {ticketsLoading && <p className="placeholder">Loading…</p>}
              {!ticketsLoading && tickets.length === 0 && (
                <p className="placeholder">
                  Nothing open — configure Jira, Azure DevOps, or Zendesk under the Integrations tab to populate this.
                </p>
              )}
              {!ticketsLoading && tickets.map((t) => (
                <div className="feed-row" key={`${t.source}-${t.id}`}>
                  <div className="row" style={{ gap: 8 }}>
                    <span className="feed-source">{integrationLabel(t.source)}</span>
                    <span className="feed-meta">#{t.id}</span>
                    {t.url ? (
                      <a href={t.url} target="_blank" rel="noreferrer">{t.title}</a>
                    ) : (
                      <span>{t.title}</span>
                    )}
                    {t.type && <span className="tag">{t.type}</span>}
                  </div>
                  <div className="row" style={{ gap: 8 }}>
                    <span className="feed-meta">{t.status}</span>
                    <span className="feed-meta">{new Date(t.updated).toLocaleString()}</span>
                    <button
                      type="button"
                      onClick={() =>
                        navigate("/investigate", {
                          state: {
                            prefillNotes: `${integrationLabel(t.source)} #${t.id}: ${t.title}`,
                            prefillDeploymentId: detail.deployments.length === 1 ? detail.deployments[0].id : null,
                          },
                        })
                      }
                    >
                      <Icon name="search" size={13} />
                      Investigate
                    </button>
                  </div>
                </div>
              ))}
              </div>
              )}

              {activeTab === "integrations" && (
              <div key="integrations" className="tab-panel">
              <p className="placeholder" style={{ marginTop: 0 }}>
                Credentials this client's own deployments use instead of the shared global default, when an
                investigation is scoped to one of this client's deployments. Configure the shared default on the{" "}
                <Link to="/settings/integrations">Integrations</Link> page.
              </p>
              {clientIntegrations.map((i) => (
                <div key={i.name}>
                  <div className="feed-row">
                    <div className="row" style={{ gap: 8 }}>
                      <span className="feed-source">{integrationLabel(i.name)}</span>
                      <span className="feed-meta">{integrationRole(i.name)}</span>
                      <span className={"badge " + (i.configured ? "ok" : "warn")}>
                        {i.configured ? "configured" : "not configured"}
                      </span>
                      {i.override && <span className="tag accent">client override</span>}
                      {!i.override && i.using_global_default && <span className="tag">shared default</span>}
                      {integrationTestResults[i.name] && (
                        <span style={{ color: integrationTestResults[i.name].ok ? "var(--ok)" : "var(--err)" }}>
                          {integrationTestResults[i.name].detail}
                        </span>
                      )}
                    </div>
                    <div className="row" style={{ gap: 8 }}>
                      {i.editable && (
                        <button
                          onClick={() =>
                            editingIntegration === i.name ? cancelEditIntegration() : startEditIntegration(i.name)
                          }
                        >
                          {editingIntegration === i.name ? "Cancel" : i.override ? "Edit" : "Set up"}
                        </button>
                      )}
                      {i.override && (
                        confirmClearIntegration === i.name ? (
                          <>
                            <span className="placeholder" style={{ fontSize: 13 }}>Clear this override?</span>
                            <button className="danger" onClick={() => clearIntegration(c.id, i.name)}>Confirm</button>
                            <button onClick={() => setConfirmClearIntegration(null)}>Cancel</button>
                          </>
                        ) : (
                          <button className="danger" onClick={() => setConfirmClearIntegration(i.name)}>
                            Clear override
                          </button>
                        )
                      )}
                      <button
                        disabled={!i.configured || testingIntegration === i.name}
                        onClick={() => testIntegration(c.id, i.name)}
                      >
                        {testingIntegration === i.name ? "Testing…" : "Test connection"}
                      </button>
                    </div>
                  </div>

                  {editingIntegration === i.name && (
                    <div style={{ padding: "4px 0 16px 0" }}>
                      <div className="row" style={{ alignItems: "flex-end" }}>
                        {(integrationFieldSchema[i.name] || []).map((f) => (
                          <div className="field" key={f.key}>
                            <label>{f.label}</label>
                            <input
                              type={f.secret ? "password" : "text"}
                              placeholder={i.override ? "Leave blank to keep current value" : "Optional"}
                              value={integrationFormValues[f.key] || ""}
                              onChange={(e) =>
                                setIntegrationFormValues((v) => ({ ...v, [f.key]: e.target.value }))
                              }
                            />
                          </div>
                        ))}
                        <button
                          className="primary"
                          disabled={savingIntegration || !Object.values(integrationFormValues).some((v) => v.trim())}
                          onClick={() => saveIntegration(c.id, i.name)}
                        >
                          <Icon name="check" size={14} />
                          {savingIntegration ? "Saving…" : "Save"}
                        </button>
                      </div>
                      {integrationSaveError && (
                        <p style={{ color: "var(--err)", fontSize: 13, margin: "8px 0 0" }}>{integrationSaveError}</p>
                      )}
                    </div>
                  )}
                </div>
              ))}
              </div>
              )}
            </div>
          )}
        </div>
      ))}
    </section>
  );
}
