using ModelContextProtocol;
using ModelContextProtocol.Server;
using System.ComponentModel;
using System.Net.Http.Headers;
using System.Text.Json;

namespace McpServer.Tools;

[McpServerToolType]
public sealed class TaskTools
{
    private readonly IHttpClientFactory _httpClientFactory;
    private readonly IHttpContextAccessor _httpContextAccessor;

    public TaskTools(IHttpClientFactory httpClientFactory, IHttpContextAccessor httpContextAccessor)
    {
        _httpClientFactory = httpClientFactory;
        _httpContextAccessor = httpContextAccessor;
    }

    private string? GetBearerToken()
    {
        var authHeader = _httpContextAccessor.HttpContext?.Request.Headers.Authorization.FirstOrDefault();
        if (authHeader is not null && authHeader.StartsWith("Bearer ", StringComparison.OrdinalIgnoreCase))
        {
            return authHeader["Bearer ".Length..];
        }
        return null;
    }

    private async Task<JsonDocument> CallProjectApi(HttpMethod method, string path, object? body = null)
    {
        var token = GetBearerToken()
            ?? throw new McpException("No bearer token available. Please authenticate first.");

        var client = _httpClientFactory.CreateClient("ProjectApi");
        var request = new HttpRequestMessage(method, path);
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);

        if (body is not null)
        {
            request.Content = JsonContent.Create(body);
        }

        var response = await client.SendAsync(request);

        if (response.StatusCode == System.Net.HttpStatusCode.Unauthorized)
            throw new McpException("Authentication failed. Your token may be invalid or expired.");
        if (response.StatusCode == System.Net.HttpStatusCode.Forbidden)
            throw new McpException("Permission denied. You don't have the required scope for this operation.");
        if (response.StatusCode == System.Net.HttpStatusCode.NotFound)
            throw new McpException($"Resource not found: {path}");

        response.EnsureSuccessStatusCode();
        return await response.Content.ReadFromJsonAsync<JsonDocument>()
            ?? throw new McpException("Empty response from project API.");
    }

    private static string FormatTask(JsonElement task) =>
        $"""
        [{task.GetProperty("id").GetString()}] {task.GetProperty("title").GetString()}
          Assignee: {task.GetProperty("assignee").GetString() ?? "unassigned"}
          Status:   {task.GetProperty("status").GetString() ?? "unknown"}
          Priority: {task.GetProperty("priority").GetString() ?? "unknown"}
        """;

    [McpServerTool, Description("List all tasks in the project. Requires tasks:read scope.")]
    public async Task<string> ListTasks()
    {
        using var doc = await CallProjectApi(HttpMethod.Get, "/tasks");
        var tasks = doc.RootElement.EnumerateArray().ToList();

        if (tasks.Count == 0)
            return "No tasks found.";

        var lines = new List<string> { $"Found {tasks.Count} task(s):\n" };
        foreach (var task in tasks)
        {
            lines.Add(FormatTask(task));
        }
        return string.Join("\n", lines);
    }

    [McpServerTool, Description("Get details of a specific task. Requires tasks:read scope.")]
    public async Task<string> GetTask(
        [Description("The task identifier (e.g. TASK-001)")] string taskId)
    {
        using var doc = await CallProjectApi(HttpMethod.Get, $"/tasks/{taskId}");
        return FormatTask(doc.RootElement);
    }

    [McpServerTool, Description("Create a new task in the project. Requires tasks:admin scope.")]
    public async Task<string> CreateTask(
        [Description("The task title")] string title,
        [Description("Who the task is assigned to (optional)")] string? assignee = null,
        [Description("Task priority - low, medium, high, critical (default: medium)")] string? priority = "medium")
    {
        var body = new Dictionary<string, string?> { ["title"] = title };
        if (assignee is not null) body["assignee"] = assignee;
        if (priority is not null) body["priority"] = priority;

        using var doc = await CallProjectApi(HttpMethod.Post, "/tasks", body);
        return $"Task created successfully:\n\n{FormatTask(doc.RootElement)}";
    }

    [McpServerTool, Description("Close a completed task. Requires tasks:admin scope.")]
    public async Task<string> CloseTask(
        [Description("The task identifier to close (e.g. TASK-003)")] string taskId)
    {
        using var doc = await CallProjectApi(HttpMethod.Patch, $"/tasks/{taskId}/close");
        return $"Task closed successfully:\n\n{FormatTask(doc.RootElement)}";
    }
}
