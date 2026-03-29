using System.Text.RegularExpressions;

namespace LogicalToolsServer.Services;

/// <summary>
/// Status normalization and state machine validation for MadeUpTasks statuses.
/// </summary>
public sealed partial class StatusHelper
{
    public static readonly Dictionary<string, List<string>> ValidTransitions = new()
    {
        ["open"] = ["in_progress", "blocked"],
        ["in_progress"] = ["in-review", "blocked"],
        ["in-review"] = ["done", "in_progress"],
        ["blocked"] = ["open", "in_progress"],
        ["done"] = [],
    };

    private static readonly Dictionary<string, string> StatusAliases = new()
    {
        ["open"] = "open", ["opened"] = "open", ["new"] = "open",
        ["todo"] = "open", ["to do"] = "open", ["to_do"] = "open",
        ["in_progress"] = "in_progress", ["in progress"] = "in_progress",
        ["in-progress"] = "in_progress", ["inprogress"] = "in_progress",
        ["wip"] = "in_progress", ["working"] = "in_progress",
        ["in_review"] = "in-review", ["in review"] = "in-review",
        ["in-review"] = "in-review", ["inreview"] = "in-review",
        ["review"] = "in-review", ["reviewing"] = "in-review",
        ["done"] = "done", ["closed"] = "done", ["complete"] = "done",
        ["completed"] = "done", ["finished"] = "done", ["resolved"] = "done",
        ["blocked"] = "blocked", ["stuck"] = "blocked",
    };

    public string Normalize(string status)
    {
        var key = WhitespacePattern().Replace(status.Trim().ToLowerInvariant(), " ");
        if (StatusAliases.TryGetValue(key, out var canonical))
            return canonical;

        var valid = string.Join(", ", StatusAliases.Values.Distinct().Order());
        throw new ArgumentException($"Unrecognised status '{status}'. Valid statuses are: {valid}");
    }

    /// <summary>BFS through the state machine to find the shortest transition path.</summary>
    public List<string>? FindPath(string from, string to)
    {
        if (from == to) return [from];
        var queue = new Queue<List<string>>();
        queue.Enqueue([from]);
        var visited = new HashSet<string> { from };

        while (queue.Count > 0)
        {
            var path = queue.Dequeue();
            if (!ValidTransitions.TryGetValue(path[^1], out var nexts)) continue;
            foreach (var next in nexts)
            {
                if (visited.Contains(next)) continue;
                var newPath = new List<string>(path) { next };
                if (next == to) return newPath;
                visited.Add(next);
                queue.Enqueue(newPath);
            }
        }
        return null;
    }

    [GeneratedRegex(@"[\s_-]+")]
    private static partial Regex WhitespacePattern();
}
