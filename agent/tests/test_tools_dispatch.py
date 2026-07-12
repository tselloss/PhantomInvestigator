import tools


def test_execute_tool_threads_deployment_id_to_jira(monkeypatch):
    monkeypatch.setattr(tools.jira, "get_ticket", lambda key, user_id, deployment_id=None: f"key={key} dep={deployment_id} user={user_id}")
    assert tools.execute_tool("get_jira_ticket", {"key": "OPS-1", "deployment_id": 42}, 1) == "key=OPS-1 dep=42 user=1"


def test_execute_tool_deployment_id_defaults_to_none(monkeypatch):
    monkeypatch.setattr(tools.jira, "get_ticket", lambda key, user_id, deployment_id=None: deployment_id)
    assert tools.execute_tool("get_jira_ticket", {"key": "OPS-1"}, 1) is None


def test_execute_tool_threads_deployment_id_to_azure_devops_work_item(monkeypatch):
    monkeypatch.setattr(
        tools.azure_devops, "get_work_item", lambda work_item_id, user_id, deployment_id=None: deployment_id
    )
    assert tools.execute_tool("get_azure_devops_work_item", {"work_item_id": 42, "deployment_id": 7}, 1) == 7


def test_execute_tool_threads_deployment_id_to_azure_devops_commits(monkeypatch):
    monkeypatch.setattr(
        tools.azure_devops, "get_recent_commits", lambda user_id, deployment_id=None, days=7: (deployment_id, days)
    )
    assert tools.execute_tool("get_azure_devops_commits", {"deployment_id": 7}, 1) == (7, 7)
    assert tools.execute_tool("get_azure_devops_commits", {"deployment_id": 7, "days": 3}, 1) == (7, 3)


def test_execute_tool_threads_deployment_id_to_azure_devops_builds(monkeypatch):
    monkeypatch.setattr(
        tools.azure_devops, "get_recent_builds",
        lambda user_id, deployment_id=None, hours=24, failed_only=False: (deployment_id, hours, failed_only),
    )
    assert tools.execute_tool("get_azure_devops_builds", {"deployment_id": 7}, 1) == (7, 24, False)
    assert tools.execute_tool(
        "get_azure_devops_builds", {"deployment_id": 7, "hours": 6, "failed_only": True}, 1
    ) == (7, 6, True)


def test_execute_tool_threads_deployment_id_to_azure_devops_work_item_search(monkeypatch):
    monkeypatch.setattr(
        tools.azure_devops, "search_work_items",
        lambda query, user_id, deployment_id=None, days=7: (query, deployment_id, days),
    )
    assert tools.execute_tool(
        "search_azure_devops_work_items", {"query": "checkout", "deployment_id": 7}, 1
    ) == ("checkout", 7, 7)


def test_execute_tool_threads_deployment_id_to_query_metrics(monkeypatch):
    monkeypatch.setattr(tools.prometheus, "query", lambda promql, user_id, deployment_id=None: deployment_id)
    assert tools.execute_tool("query_metrics", {"promql": "up", "deployment_id": 7}, 1) == 7


def test_execute_tool_threads_deployment_id_to_search_logs(monkeypatch):
    monkeypatch.setattr(tools.loki, "search", lambda logql, user_id, minutes, deployment_id=None: deployment_id)
    assert tools.execute_tool("search_logs", {"logql": "{}", "deployment_id": 7}, 1) == 7


def test_execute_tool_threads_deployment_id_to_github_runs(monkeypatch):
    monkeypatch.setattr(tools.github_actions, "get_recent_runs", lambda repo, user_id, deployment_id=None: deployment_id)
    assert tools.execute_tool("get_github_runs", {"repo": "owner/repo", "deployment_id": 7}, 1) == 7


def test_execute_tool_threads_deployment_id_to_github_run_logs(monkeypatch):
    monkeypatch.setattr(
        tools.github_actions, "get_run_logs", lambda repo, run_id, user_id, deployment_id=None: deployment_id
    )
    assert tools.execute_tool("get_github_run_logs", {"repo": "owner/repo", "run_id": 1, "deployment_id": 7}, 1) == 7


def test_execute_tool_threads_deployment_id_to_deploy_diff(monkeypatch):
    monkeypatch.setattr(
        tools.github_actions, "get_deploy_diff", lambda repo, base, head, user_id, deployment_id=None: deployment_id
    )
    assert tools.execute_tool(
        "get_deploy_diff", {"repo": "owner/repo", "base": "main", "head": "feature", "deployment_id": 7}, 1
    ) == 7


def test_execute_tool_threads_deployment_id_to_azure_logs(monkeypatch):
    monkeypatch.setattr(tools.azure_monitor, "query_logs", lambda kql, user_id, deployment_id=None: deployment_id)
    assert tools.execute_tool("query_azure_logs", {"kql": "Traces", "deployment_id": 7}, 1) == 7


def test_execute_tool_threads_deployment_id_to_azure_metrics(monkeypatch):
    monkeypatch.setattr(
        tools.azure_monitor, "query_metrics",
        lambda resource_id, metric_namespace, metric_names, user_id, deployment_id=None: deployment_id,
    )
    assert tools.execute_tool(
        "query_azure_metrics",
        {"resource_id": "/subscriptions/x", "metric_namespace": "ns", "metric_names": "m", "deployment_id": 7},
        1,
    ) == 7


def test_execute_tool_threads_deployment_id_to_aws_logs(monkeypatch):
    monkeypatch.setattr(
        tools.aws_cloudwatch, "query_logs",
        lambda log_group, filter_pattern, user_id, minutes, deployment_id=None: deployment_id,
    )
    assert tools.execute_tool(
        "query_aws_logs", {"log_group": "g", "filter_pattern": "p", "deployment_id": 7}, 1
    ) == 7


def test_execute_tool_threads_deployment_id_to_aws_metrics(monkeypatch):
    monkeypatch.setattr(
        tools.aws_cloudwatch, "query_metrics",
        lambda namespace, metric_name, user_id, dimensions_json, deployment_id=None: deployment_id,
    )
    assert tools.execute_tool(
        "query_aws_metrics", {"namespace": "AWS/EC2", "metric_name": "CPUUtilization", "deployment_id": 7}, 1
    ) == 7


def test_execute_tool_threads_deployment_id_to_support_tickets(monkeypatch):
    monkeypatch.setattr(tools.zendesk, "search_tickets", lambda query, user_id, deployment_id=None: deployment_id)
    assert tools.execute_tool("search_support_tickets", {"query": "checkout", "deployment_id": 7}, 1) == 7
