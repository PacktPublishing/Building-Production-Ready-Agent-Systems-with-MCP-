using LogicalToolsServer.Services;
using ModelContextProtocol.Server;
using System.ComponentModel;
using System.Text.Json;

namespace LogicalToolsServer.Tools;

/// <summary>
/// Seven tools wrapping the MadeUpTasks REST API with response shaping,
/// status normalization, and user-name resolution.
/// </summary>
[McpServerToolType]
public sealed class LogicalTools(ApiClient api, StatusHelper statusHelper, UserResolver userResolver)
{
    private static readonly JsonSerializerOptions s_jsonOptions = new() { WriteIndented = true };
    private static string Json(object obj) => JsonSerializer.Serialize(obj, s_jsonOptions);

    private static bool IsOverdue(JsonElement task)
    {
        if (!task.TryGetProperty("due_date", out var dd) || dd.ValueKind != JsonValueKind.String)
            return false;
        return DateTimeOffset.TryParse(dd.GetString(), out var dt) && dt.Date < DateTimeOffset.UtcNow.Date;
    }

    [McpServerTool, Description("""
        List all projects the current user has access to.
        Returns each project's ID, name, status, and description.
        """)]
    public async Task<string> ListProjects()
    {
        var data = await api.GetAsync("projects");
        var projects = data.ValueKind == JsonValueKind.Array ? data.EnumerateArray().ToList() : [];
        var results = projects.Select(p => new
        {
            id = p.GetProperty("id").GetString(),
            name = p.GetProperty("name").GetString(),
            status = p.TryGetProperty("status", out var s) ? s.GetString() : null,
            description = p.TryGetProperty("description", out var d) ? d.GetString() : null,
        });
        return Json(new { projects = results, count = projects.Count });
    }

    [McpServerTool, Description("""
        Get a complete overview of a project including its members and task summary.
        Returns project details, team members with roles, and a breakdown of tasks
        by status with lists of blocked and overdue tasks.
        """)]
    public async Task<string> GetProjectOverview(
        [Description("The project identifier (e.g. prj_001)")] string projectId)
    {
        var projectTask = api.GetAsync($"projects/{projectId}");
        var membersTask = api.GetAsync($"projects/{projectId}/members");
        var tasksTask = FetchAllProjectTasks(projectId);
        await Task.WhenAll(projectTask, membersTask, tasksTask);

        var project = await projectTask;
        var members = (await membersTask).EnumerateArray().ToList();
        var tasks = await tasksTask;

        var ownerName = await userResolver.GetNameAsync(
            project.TryGetProperty("owner_id", out var oid) ? oid.GetString() : null);

        var statusCounts = new Dictionary<string, int>();
        var blocked = new List<object>();
        var overdue = new List<object>();

        foreach (var t in tasks)
        {
            var st = t.TryGetProperty("status", out var s) ? s.GetString() ?? "unknown" : "unknown";
            statusCounts[st] = statusCounts.GetValueOrDefault(st) + 1;

            var assigneeId = t.TryGetProperty("assignee_id", out var a) ? a.GetString() : null;
            var assigneeName = members
                .Where(m => m.TryGetProperty("user_id", out var u) && u.GetString() == assigneeId)
                .Select(m => m.TryGetProperty("name", out var n) ? n.GetString() : null)
                .FirstOrDefault() ?? "Unassigned";

            if (st == "blocked")
                blocked.Add(new { title = t.GetProperty("title").GetString(), assignee = assigneeName });

            if (st != "done" && IsOverdue(t))
                overdue.Add(new
                {
                    title = t.GetProperty("title").GetString(),
                    due_date = t.GetProperty("due_date").GetString(),
                    assignee = assigneeName,
                });
        }

        return Json(new
        {
            project = new
            {
                name = project.GetProperty("name").GetString(),
                description = project.TryGetProperty("description", out var desc) ? desc.GetString() : null,
                status = project.TryGetProperty("status", out var ps) ? ps.GetString() : null,
                owner = ownerName,
            },
            members = members.Select(m => new
            {
                name = m.TryGetProperty("name", out var n) ? n.GetString() : null,
                role = m.TryGetProperty("role", out var r) ? r.GetString() : null,
            }),
            task_summary = new { total = tasks.Count, by_status = statusCounts },
            blocked_tasks = blocked,
            overdue_tasks = overdue,
        });
    }

    [McpServerTool, Description("""
        Search for tasks across all projects. Returns matching tasks with key fields only.
        Assignee can be a name (e.g. "Bob") or user ID. Status accepts any format
        (e.g. "in progress", "IN_REVIEW", "wip").
        """)]
    public async Task<string> SearchTasks(
        [Description("Full-text search query")] string? query = null,
        [Description("Filter by project ID")] string? projectId = null,
        [Description("Filter by status (any format)")] string? status = null,
        [Description("Filter by assignee name or user ID")] string? assignee = null,
        [Description("Max results (default 10)")] int limit = 10)
    {
        var queryParams = new Dictionary<string, string> { ["per_page"] = Math.Min(limit, 50).ToString() };
        if (query is not null) queryParams["q"] = query;
        if (projectId is not null) queryParams["project_id"] = projectId;
        if (status is not null) queryParams["status"] = statusHelper.Normalize(status);
        if (assignee is not null) queryParams["assignee_id"] = await userResolver.ResolveAsync(assignee);

        var data = await api.GetAsync("tasks/search", queryParams);
        var items = data.ValueKind == JsonValueKind.Array ? data.EnumerateArray().ToList() : [];

        var results = new List<object>();
        foreach (var t in items)
            results.Add(await ShapeTask(t));

        // Fuzzy near-miss matching when exact search returns nothing
        List<object>? nearMisses = null;
        if (items.Count == 0 && query is not null)
        {
            var allParams = new Dictionary<string, string> { ["per_page"] = "100" };
            if (projectId is not null) allParams["project_id"] = projectId;
            var allData = await api.GetAsync("tasks/search", allParams);
            var allTasks = allData.ValueKind == JsonValueKind.Array ? allData.EnumerateArray().ToList() : [];

            var scored = new List<(double score, JsonElement task)>();
            foreach (var t in allTasks)
            {
                var title = t.TryGetProperty("title", out var tt) ? tt.GetString() ?? "" : "";
                var desc = t.TryGetProperty("description", out var dd) ? dd.GetString() ?? "" : "";
                var score = Math.Max(WordOverlap(query, title), WordOverlap(query, desc) * 0.7);
                if (score > 0) scored.Add((score, t));
            }

            scored.Sort((a, b) => b.score.CompareTo(a.score));
            if (scored.Count > 0)
            {
                nearMisses = [];
                foreach (var (score, t) in scored.Take(5))
                {
                    var shaped = await ShapeTask(t);
                    var quality = score >= 0.6 ? "high" : score >= 0.3 ? "medium" : "low";
                    nearMisses.Add(new { shaped, match_quality = quality });
                }
            }
        }

        if (nearMisses is not null)
            return Json(new { tasks = results, count = results.Count, no_exact_matches = true, nearest_tasks = nearMisses });
        return Json(new { tasks = results, count = results.Count });
    }

    [McpServerTool, Description("""
        Get full details of a specific task including its recent comments.
        Returns essential task fields and the latest 5 comments with author names.
        """)]
    public async Task<string> GetTaskDetails(
        [Description("The task identifier (e.g. tsk_001)")] string taskId)
    {
        var taskData = api.GetAsync($"tasks/{taskId}");
        var commentsData = api.GetAsync($"tasks/{taskId}/comments", new() { ["limit"] = "5" });
        await Task.WhenAll(taskData, commentsData);

        var task = await taskData;
        var comments = await commentsData;
        var assigneeName = await userResolver.GetNameAsync(
            task.TryGetProperty("assignee_id", out var a) ? a.GetString() : null);

        var shapedComments = new List<object>();
        if (comments.ValueKind == JsonValueKind.Array)
        {
            foreach (var c in comments.EnumerateArray().Take(5))
            {
                var authorId = c.TryGetProperty("author_id", out var ai) ? ai.GetString() : null;
                var authorName = await userResolver.GetNameAsync(authorId);
                var commentTimestamp = c.TryGetProperty("created_at", out var cca) ? cca.GetString() : null;
                var commentBody = c.TryGetProperty("body", out var cb) ? cb.GetString() ?? "" : "";
                shapedComments.Add(new
                {
                    author = authorName,
                    timestamp = commentTimestamp,
                    body = commentBody.Length > 500 ? commentBody[..500] : commentBody,
                });
            }
        }

        return Json(new
        {
            task = new
            {
                id = task.GetProperty("id").GetString(),
                title = task.GetProperty("title").GetString(),
                description = task.TryGetProperty("description", out var d) ? d.GetString() : null,
                status = task.TryGetProperty("status", out var s) ? s.GetString() : null,
                priority = task.TryGetProperty("priority", out var p) ? p.GetString() : null,
                assignee = assigneeName,
                due_date = task.TryGetProperty("due_date", out var dd) ? dd.GetString() : null,
                labels = task.TryGetProperty("labels", out var l) ? l : default,
                created_at = task.TryGetProperty("created_at", out var ca) ? ca.GetString() : null,
            },
            recent_comments = shapedComments,
        });
    }

    [McpServerTool, Description("""
        Change the status of a task. Validates the transition is allowed.
        Accepts any status format (e.g. "in progress", "IN_REVIEW"). If the transition
        is not directly allowed, suggests the shortest multi-step path.
        """)]
    public async Task<string> UpdateTaskStatus(
        [Description("The task identifier")] string taskId,
        [Description("Target status (any format)")] string newStatus)
    {
        var normalized = statusHelper.Normalize(newStatus);
        var task = await api.GetAsync($"tasks/{taskId}");
        var currentStatus = task.TryGetProperty("status", out var s) ? s.GetString() ?? "" : "";

        if (!StatusHelper.ValidTransitions.TryGetValue(currentStatus, out var allowed) || !allowed.Contains(normalized))
        {
            var path = statusHelper.FindPath(currentStatus, normalized);
            var result = new Dictionary<string, object?>
            {
                ["error"] = $"Cannot transition directly from '{currentStatus}' to '{normalized}'.",
                ["current_status"] = currentStatus,
                ["allowed_transitions_from_current"] = StatusHelper.ValidTransitions.GetValueOrDefault(currentStatus, []),
            };
            if (path is { Count: > 2 })
            {
                result["suggested_path"] = path;
                result["next_step"] = path[1];
                result["hint"] = $"To reach '{normalized}', transition through: {string.Join(" → ", path)}. Call UpdateTaskStatus with '{path[1]}' as the next step.";
            }
            else if (path is null)
            {
                result["hint"] = $"There is no valid path from '{currentStatus}' to '{normalized}'.";
            }
            return Json(result);
        }

        var data = await api.PostAsync($"tasks/{taskId}/transition", new { to = normalized });
        var hints = new List<string>();
        if ((!task.TryGetProperty("assignee_id", out var aid) || aid.ValueKind == JsonValueKind.Null) && normalized == "in_progress")
            hints.Add("This task has no assignee — it's now in progress but nobody is responsible for it.");
        if (IsOverdue(task))
            hints.Add($"This task is past its due date ({task.GetProperty("due_date").GetString()}).");
        if (normalized == "done")
            hints.Add("Task is now closed. No further transitions are possible.");

        var newStatusValue = data.TryGetProperty("new_status", out var nsVal) ? nsVal.GetString() ?? "" : "";
        var response = new Dictionary<string, object?>
        {
            ["task_id"] = taskId,
            ["task_title"] = data.TryGetProperty("title", out var tVal) ? tVal.GetString() : null,
            ["previous_status"] = data.TryGetProperty("previous_status", out var psVal) ? psVal.GetString() : null,
            ["new_status"] = newStatusValue,
            ["available_next_transitions"] = StatusHelper.ValidTransitions.GetValueOrDefault(newStatusValue, []),
            ["timestamp"] = data.TryGetProperty("updated_at", out var uaVal) ? uaVal.GetString() : null,
        };
        if (hints.Count > 0) response["hints"] = hints;
        return Json(response);
    }

    [McpServerTool, Description("""
        Create a new task in a project. Assignee can be specified by name.
        Returns confirmation with the created task's key fields.
        """)]
    public async Task<string> CreateTask(
        [Description("The project identifier (e.g. prj_001)")] string projectId,
        [Description("The task title")] string title,
        [Description("Optional description")] string? description = null,
        [Description("Assignee name or user ID")] string? assignee = null,
        [Description("Priority: low, medium, high (default medium)")] string priority = "medium",
        [Description("Due date in ISO format")] string? dueDate = null)
    {
        string? assigneeId = null;
        if (assignee is not null)
            assigneeId = await userResolver.ResolveAsync(assignee);

        var payload = new Dictionary<string, string> { ["title"] = title, ["priority"] = priority };
        if (description is not null) payload["description"] = description;
        if (assigneeId is not null) payload["assignee_id"] = assigneeId;
        if (dueDate is not null) payload["due_date"] = dueDate;

        var data = await api.PostAsync($"projects/{projectId}/tasks", payload);
        var assigneeName = await userResolver.GetNameAsync(
            data.TryGetProperty("assignee_id", out var a) ? a.GetString() : null);

        return Json(new
        {
            created = true,
            task = new
            {
                id = data.GetProperty("id").GetString(),
                title = data.GetProperty("title").GetString(),
                status = data.TryGetProperty("status", out var s) ? s.GetString() : null,
                assignee = assigneeName,
                project_id = projectId,
                priority = data.TryGetProperty("priority", out var p) ? p.GetString() : null,
                due_date = data.TryGetProperty("due_date", out var dd) ? dd.GetString() : null,
            },
        });
    }

    [McpServerTool, Description("Add a comment to a task. Returns the comment ID, author, timestamp, and body preview.")]
    public async Task<string> AddComment(
        [Description("The task identifier")] string taskId,
        [Description("The comment text")] string comment)
    {
        var data = await api.PostAsync($"tasks/{taskId}/comments", new { body = comment });
        var authorName = await userResolver.GetNameAsync(
            data.TryGetProperty("author_id", out var a) ? a.GetString() : null);
        var body = data.TryGetProperty("body", out var b) ? b.GetString() ?? comment : comment;

        return Json(new
        {
            comment_id = data.TryGetProperty("id", out var id) ? id.GetString() : null,
            task_id = taskId,
            author = authorName,
            timestamp = data.TryGetProperty("created_at", out var ca) ? ca.GetString() : null,
            body_preview = body.Length > 200 ? body[..200] : body,
        });
    }

    // -- Helpers --

    private async Task<object> ShapeTask(JsonElement t) => new
    {
        id = t.TryGetProperty("id", out var id) ? id.GetString() : null,
        title = t.TryGetProperty("title", out var ti) ? ti.GetString() : null,
        status = t.TryGetProperty("status", out var s) ? s.GetString() : null,
        assignee = await userResolver.GetNameAsync(t.TryGetProperty("assignee_id", out var a) ? a.GetString() : null),
        project_id = t.TryGetProperty("project_id", out var p) ? p.GetString() : null,
        priority = t.TryGetProperty("priority", out var pr) ? pr.GetString() : null,
        due_date = t.TryGetProperty("due_date", out var d) ? d.GetString() : null,
    };

    private async Task<List<JsonElement>> FetchAllProjectTasks(string projectId)
    {
        var tasks = new List<JsonElement>();
        string? cursor = null;
        while (true)
        {
            var queryParams = new Dictionary<string, string> { ["limit"] = "100" };
            if (cursor is not null) queryParams["cursor"] = cursor;
            var raw = await api.GetRawAsync($"projects/{projectId}/tasks", queryParams);
            if (raw.TryGetProperty("data", out var data) && data.ValueKind == JsonValueKind.Array)
                tasks.AddRange(data.EnumerateArray());
            if (!raw.TryGetProperty("pagination", out var pag) ||
                !pag.TryGetProperty("has_more", out var hm) || !hm.GetBoolean())
                break;
            cursor = pag.TryGetProperty("next_cursor", out var nc) ? nc.GetString() : null;
            if (cursor is null) break;
        }
        return tasks;
    }

    private static double WordOverlap(string query, string text)
    {
        if (string.IsNullOrEmpty(query) || string.IsNullOrEmpty(text)) return 0;
        var qWords = query.ToLowerInvariant().Split(' ', StringSplitOptions.RemoveEmptyEntries).ToHashSet();
        var tWords = text.ToLowerInvariant().Split(' ', StringSplitOptions.RemoveEmptyEntries).ToHashSet();
        if (qWords.Count == 0) return 0;
        return (double)qWords.Intersect(tWords).Count() / qWords.Count;
    }
}
