using ModelContextProtocol;
using ModelContextProtocol.Server;
using System.ComponentModel;
using System.Net.Http.Json;
using System.Text.Json;

namespace BaselineServer;

/// <summary>
/// Baseline MCP tools — raw API passthrough with no shaping or filtering.
/// Deliberately returns full raw responses to demonstrate the cost of
/// unoptimized tool design (40+ fields per task, pagination metadata, etc.).
/// </summary>
[McpServerToolType]
public sealed class BaselineTools(IHttpClientFactory httpClientFactory)
{
    private static readonly JsonSerializerOptions s_jsonOptions = new() { WriteIndented = true };

    private async Task<string> Dump(HttpResponseMessage response)
    {
        var json = await response.Content.ReadFromJsonAsync<JsonElement>();
        return JsonSerializer.Serialize(json, s_jsonOptions);
    }

    private HttpClient Api() => httpClientFactory.CreateClient("MadeUpTasksApi");

    [McpServerTool, Description("""
        List all tasks in a MadeUpTasks project.
        The project_id parameter should be the internal project identifier (e.g. prj_001).
        Returns the full raw response including all fields, pagination metadata, audit trails,
        webhook configurations, SLA tiers, compliance tags, time tracking data, and risk scores.
        """)]
    public async Task<string> ListTasks(
        [Description("The internal project identifier (e.g. prj_001)")] string projectId)
    {
        var response = await Api().GetAsync($"projects/{projectId}/tasks");
        return await Dump(response);
    }

    [McpServerTool, Description("""
        Get complete details for a single MadeUpTasks task.
        Returns the full task object including all metadata fields, audit trail,
        webhook configuration, SLA tier, compliance tags, time tracking, risk score,
        cost allocation, dependency IDs, and custom fields.
        """)]
    public async Task<string> GetTask(
        [Description("The task identifier (e.g. tsk_001)")] string taskId)
    {
        var response = await Api().GetAsync($"tasks/{taskId}");
        return await Dump(response);
    }

    [McpServerTool, Description("""
        Create a new task in a MadeUpTasks project.
        Note: assignee_id must be the internal user ID (e.g. usr_002), not the user's name.
        """)]
    public async Task<string> CreateTask(
        [Description("The internal project identifier (e.g. prj_001)")] string projectId,
        [Description("The task title")] string title,
        [Description("Optional description text")] string? description = null,
        [Description("The internal user ID to assign to (e.g. usr_002)")] string? assigneeId = null,
        [Description("One of: low, medium, high")] string? priority = null)
    {
        var body = new Dictionary<string, string> { ["title"] = title };
        if (description is not null) body["description"] = description;
        if (assigneeId is not null) body["assignee_id"] = assigneeId;
        if (priority is not null) body["priority"] = priority;

        var response = await Api().PostAsJsonAsync($"projects/{projectId}/tasks", body);
        return await Dump(response);
    }

    [McpServerTool, Description("""
        Search for tasks across all MadeUpTasks projects.
        Status must be exact canonical value: open, in_progress, in-review, done, or blocked.
        Assignee filtering requires the internal user ID, not the user's name.
        """)]
    public async Task<string> SearchTasks(
        [Description("Full-text search query")] string? q = null,
        [Description("Filter by status (exact canonical value)")] string? status = null,
        [Description("Filter by internal user ID (e.g. usr_002)")] string? assigneeId = null,
        [Description("Filter by project ID (e.g. prj_001)")] string? projectId = null)
    {
        var query = new List<string>();
        if (q is not null) query.Add($"q={Uri.EscapeDataString(q)}");
        if (status is not null) query.Add($"status={Uri.EscapeDataString(status)}");
        if (assigneeId is not null) query.Add($"assignee_id={Uri.EscapeDataString(assigneeId)}");
        if (projectId is not null) query.Add($"project_id={Uri.EscapeDataString(projectId)}");

        var qs = query.Count > 0 ? "?" + string.Join("&", query) : "";
        var response = await Api().GetAsync($"tasks/search{qs}");
        return await Dump(response);
    }

    [McpServerTool, Description("""
        Change the status of a task.
        The new_status should be one of: open, in_progress, in-review, done, blocked.
        Not all transitions are valid — the API enforces a state machine but this tool
        does not check beforehand.
        """)]
    public async Task<string> UpdateTaskStatus(
        [Description("The task identifier")] string taskId,
        [Description("Target status")] string newStatus)
    {
        var response = await Api().PostAsJsonAsync($"tasks/{taskId}/transition", new { to = newStatus });
        return await Dump(response);
    }

    [McpServerTool, Description("List all projects the current user has access to.")]
    public async Task<string> GetAllProjects()
    {
        var response = await Api().GetAsync("projects");
        return await Dump(response);
    }
}
