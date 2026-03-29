using System.Text.Json;

namespace MetaToolsServer.Services;

/// <summary>
/// Loads and queries the MadeUpTasks endpoint manifest.
/// </summary>
public sealed class EndpointManifest
{
    private readonly Dictionary<string, JsonElement> _groups;

    public EndpointManifest()
    {
        var manifestPath = Path.Combine(AppContext.BaseDirectory, "endpoint_manifest.json");
        if (!File.Exists(manifestPath))
            manifestPath = Path.Combine(Directory.GetCurrentDirectory(), "endpoint_manifest.json");

        var json = File.ReadAllText(manifestPath);
        var doc = JsonDocument.Parse(json);
        _groups = new Dictionary<string, JsonElement>(StringComparer.OrdinalIgnoreCase);

        foreach (var prop in doc.RootElement.GetProperty("groups").EnumerateObject())
            _groups[prop.Name] = prop.Value;
    }

    public List<object> GetGroups() =>
        _groups.Select(kv => (object)new
        {
            name = kv.Key,
            description = kv.Value.GetProperty("description").GetString(),
            endpoint_count = kv.Value.GetProperty("endpoints").GetArrayLength(),
        }).ToList();

    public List<object>? GetEndpointsByGroup(string group)
    {
        if (!_groups.TryGetValue(group, out var grp))
            return null;

        return grp.GetProperty("endpoints").EnumerateArray().Select(ep => (object)new
        {
            method = ep.GetProperty("method").GetString(),
            path = ep.GetProperty("path").GetString(),
            summary = ep.GetProperty("summary").GetString(),
        }).ToList();
    }

    public List<object> Search(string query)
    {
        var q = query.ToLowerInvariant();
        var results = new List<object>();

        foreach (var (groupName, group) in _groups)
        {
            foreach (var ep in group.GetProperty("endpoints").EnumerateArray())
            {
                var searchable = string.Join(" ",
                    ep.TryGetProperty("summary", out var s) ? s.GetString() ?? "" : "",
                    ep.TryGetProperty("description", out var d) ? d.GetString() ?? "" : "",
                    ep.TryGetProperty("tags", out var tags) && tags.ValueKind == JsonValueKind.Array
                        ? string.Join(" ", tags.EnumerateArray().Select(t => t.GetString() ?? "")) : "",
                    ep.TryGetProperty("parameters", out var parms) && parms.ValueKind == JsonValueKind.Array
                        ? string.Join(" ", parms.EnumerateArray().SelectMany(p => new[]
                        {
                            p.TryGetProperty("name", out var n) ? n.GetString() ?? "" : "",
                            p.TryGetProperty("description", out var pd) ? pd.GetString() ?? "" : "",
                        })) : "");

                if (searchable.ToLowerInvariant().Contains(q))
                {
                    results.Add(new
                    {
                        group = groupName,
                        method = ep.GetProperty("method").GetString(),
                        path = ep.GetProperty("path").GetString(),
                        summary = ep.GetProperty("summary").GetString(),
                    });
                }
            }
        }
        return results;
    }

    public JsonElement? GetDetail(string method, string path)
    {
        var methodUpper = method.ToUpperInvariant();
        foreach (var group in _groups.Values)
        {
            foreach (var ep in group.GetProperty("endpoints").EnumerateArray())
            {
                if (ep.GetProperty("method").GetString() == methodUpper &&
                    ep.GetProperty("path").GetString() == path)
                    return ep;
            }
        }
        return null;
    }
}
