using System.Text.Json;
using System.Text.RegularExpressions;

namespace LogicalToolsServer.Services;

/// <summary>
/// Resolves human-readable user names to MadeUpTasks user IDs with caching.
/// </summary>
public sealed partial class UserResolver(ApiClient apiClient)
{
    private List<JsonElement>? _userCache;

    public async Task<string> ResolveAsync(string nameOrId)
    {
        if (IsUserId(nameOrId)) return nameOrId;

        var users = await FetchUsersAsync();
        var nameLower = nameOrId.Trim().ToLowerInvariant();

        // Exact match
        foreach (var user in users)
        {
            var display = GetDisplayName(user);
            if (display.ToLowerInvariant() == nameLower)
                return user.GetProperty("id").GetString()!;
        }

        // Partial/contains match
        foreach (var user in users)
        {
            var display = GetDisplayName(user);
            if (display.ToLowerInvariant().Contains(nameLower))
                return user.GetProperty("id").GetString()!;
        }

        var available = string.Join(", ", users.Select(GetDisplayName));
        throw new ArgumentException($"Could not resolve user '{nameOrId}'. Available users: {available}");
    }

    public async Task<string> GetNameAsync(string? userId)
    {
        if (string.IsNullOrEmpty(userId)) return "Unassigned";
        try
        {
            var user = await apiClient.GetAsync($"users/{userId}");
            return user.TryGetProperty("name", out var name) ? name.GetString() ?? userId : userId;
        }
        catch
        {
            return userId;
        }
    }

    private async Task<List<JsonElement>> FetchUsersAsync()
    {
        if (_userCache is not null) return _userCache;
        var data = await apiClient.GetAsync("users");
        _userCache = data.ValueKind == JsonValueKind.Array
            ? data.EnumerateArray().ToList()
            : [];
        return _userCache;
    }

    private static string GetDisplayName(JsonElement user) =>
        (user.TryGetProperty("name", out var n) ? n.GetString() : null)
        ?? (user.TryGetProperty("display_name", out var d) ? d.GetString() : null)
        ?? "?";

    private static bool IsUserId(string value) => UserIdPattern().IsMatch(value);

    [GeneratedRegex(@"^usr_\w+$")]
    private static partial Regex UserIdPattern();
}
