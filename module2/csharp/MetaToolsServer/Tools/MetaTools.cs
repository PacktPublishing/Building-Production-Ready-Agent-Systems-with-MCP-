using MetaToolsServer.Services;
using ModelContextProtocol.Server;
using System.ComponentModel;
using System.Net.Http.Json;
using System.Text.Json;

namespace MetaToolsServer.Tools;

/// <summary>
/// Four progressive-disclosure tools that let an AI agent discover,
/// explore, and execute any MadeUpTasks API endpoint.
/// </summary>
[McpServerToolType]
public sealed class MetaTools(EndpointManifest manifest, IHttpClientFactory httpClientFactory)
{
    private static readonly JsonSerializerOptions s_jsonOptions = new() { WriteIndented = true };

    [McpServerTool, Description("""
        List available API endpoint groups, or list endpoints within a specific group.
        Call without arguments to see all groups with descriptions and endpoint counts.
        Provide a group name to see the endpoints in that group.
        """)]
    public string ListEndpoints(
        [Description("Optional group name to list endpoints for")] string? group = null)
    {
        if (group is null)
            return JsonSerializer.Serialize(manifest.GetGroups(), s_jsonOptions);

        var endpoints = manifest.GetEndpointsByGroup(group);
        if (endpoints is null)
        {
            var available = manifest.GetGroups().Select(g => ((dynamic)g).name).ToList();
            return JsonSerializer.Serialize(new { error = $"Unknown group '{group}'.", available_groups = available }, s_jsonOptions);
        }
        return JsonSerializer.Serialize(endpoints, s_jsonOptions);
    }

    [McpServerTool, Description("""
        Search for API endpoints by keyword.
        Performs case-insensitive substring matching across endpoint summaries,
        descriptions, tags, and parameter names.
        """)]
    public string SearchEndpoints(
        [Description("Search query")] string query)
    {
        var results = manifest.Search(query);
        if (results.Count == 0)
            return JsonSerializer.Serialize(new { message = $"No endpoints matched '{query}'.", results = Array.Empty<object>() }, s_jsonOptions);
        return JsonSerializer.Serialize(results, s_jsonOptions);
    }

    [McpServerTool, Description("""
        Get full details for a specific API endpoint.
        Provide the HTTP method and the template path exactly as shown by
        ListEndpoints (e.g. method="GET", path="/projects/{id}").
        """)]
    public string DescribeEndpoint(
        [Description("HTTP method (GET, POST, PUT, DELETE)")] string method,
        [Description("Template path (e.g. /projects/{id})")] string path)
    {
        var detail = manifest.GetDetail(method, path);
        if (detail is null)
            return JsonSerializer.Serialize(new
            {
                error = $"No endpoint found for {method.ToUpperInvariant()} {path}.",
                hint = "Use ListEndpoints() or SearchEndpoints() to find valid endpoints.",
            }, s_jsonOptions);
        return JsonSerializer.Serialize(detail, s_jsonOptions);
    }

    [McpServerTool, Description("""
        Execute an API endpoint against the live MadeUpTasks API.
        The path should have real values substituted (e.g. /projects/prj_001, not /projects/{id}).
        Use DescribeEndpoint first to understand the expected parameters.
        """)]
    public async Task<string> ExecuteEndpoint(
        [Description("HTTP method (GET, POST, PUT, DELETE)")] string method,
        [Description("Path with real values (e.g. /projects/prj_001)")] string path,
        [Description("Optional JSON string for the request body")] string? body = null,
        [Description("Optional query string without leading ? (e.g. status=open&limit=5)")] string? query = null)
    {
        JsonElement? parsedBody = null;
        if (body is not null)
        {
            try { parsedBody = JsonDocument.Parse(body).RootElement; }
            catch (JsonException ex)
            {
                return JsonSerializer.Serialize(new { error = $"Invalid JSON body: {ex.Message}" }, s_jsonOptions);
            }
        }

        var client = httpClientFactory.CreateClient("MadeUpTasksApi");
        var url = path.TrimStart('/');
        if (query is not null) url += "?" + query;

        var request = new HttpRequestMessage(new HttpMethod(method.ToUpperInvariant()), url);
        if (parsedBody is not null)
            request.Content = JsonContent.Create(parsedBody);

        var response = await client.SendAsync(request);
        try
        {
            var result = await response.Content.ReadFromJsonAsync<JsonElement>();
            return JsonSerializer.Serialize(result, s_jsonOptions);
        }
        catch
        {
            var raw = await response.Content.ReadAsStringAsync();
            return JsonSerializer.Serialize(new { raw, status_code = (int)response.StatusCode }, s_jsonOptions);
        }
    }
}
