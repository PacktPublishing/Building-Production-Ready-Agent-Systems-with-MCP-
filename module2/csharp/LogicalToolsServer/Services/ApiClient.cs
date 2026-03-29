using System.Net.Http.Json;
using System.Text.Json;

namespace LogicalToolsServer.Services;

/// <summary>
/// Async HTTP wrapper around the MadeUpTasks REST API.
/// Unwraps the standard API envelope and provides friendly error messages.
/// </summary>
public sealed class ApiClient(IHttpClientFactory httpClientFactory)
{
    public async Task<JsonElement> GetAsync(string path, Dictionary<string, string>? queryParams = null)
    {
        var client = httpClientFactory.CreateClient("MadeUpTasksApi");
        var qs = queryParams is { Count: > 0 }
            ? "?" + string.Join("&", queryParams.Select(p => $"{p.Key}={Uri.EscapeDataString(p.Value)}"))
            : "";
        var response = await client.GetAsync($"{path}{qs}");
        return await HandleResponse(response);
    }

    public async Task<JsonElement> GetRawAsync(string path, Dictionary<string, string>? queryParams = null)
    {
        var client = httpClientFactory.CreateClient("MadeUpTasksApi");
        var qs = queryParams is { Count: > 0 }
            ? "?" + string.Join("&", queryParams.Select(p => $"{p.Key}={Uri.EscapeDataString(p.Value)}"))
            : "";
        var response = await client.GetAsync($"{path}{qs}");
        EnsureSuccess(response);
        return await response.Content.ReadFromJsonAsync<JsonElement>();
    }

    public async Task<JsonElement> PostAsync(string path, object? body = null)
    {
        var client = httpClientFactory.CreateClient("MadeUpTasksApi");
        var response = await client.PostAsJsonAsync(path, body);
        return await HandleResponse(response);
    }

    private static async Task<JsonElement> HandleResponse(HttpResponseMessage response)
    {
        EnsureSuccess(response);
        var doc = await response.Content.ReadFromJsonAsync<JsonElement>();
        // Unwrap the standard API envelope
        if (doc.ValueKind == JsonValueKind.Object && doc.TryGetProperty("data", out var data))
            return data;
        return doc;
    }

    private static void EnsureSuccess(HttpResponseMessage response)
    {
        if (response.IsSuccessStatusCode) return;

        var status = (int)response.StatusCode;
        var msg = status switch
        {
            401 => "Authentication failed. Check MADEUPTASKS_API_TOKEN.",
            403 => "Permission denied.",
            404 => "Resource not found.",
            409 => "Conflict.",
            422 => "Validation error.",
            _ => $"MadeUpTasks API error ({status})."
        };
        throw new InvalidOperationException(msg);
    }
}
