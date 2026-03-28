using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Microsoft.Extensions.AI;

namespace SaveToFile;

/// <summary>
/// Wraps an MCP tool (or any AIFunction) to save large results to files.
///
/// When the tool returns text content exceeding a configurable threshold,
/// the full result is written to disk and replaced with a compact summary
/// containing the file path and a preview.
///
/// This is done by extending DelegatingAIFunction, which transparently
/// delegates Name, Description, and Schema to the inner tool — making
/// this wrapper invisible to the model's tool selection logic.
///
/// Why this matters:
/// - Tool results are included in the model's context on every subsequent turn
/// - A 10K-token result in a 5-turn conversation costs 50K input tokens
/// - Saving to file and returning a 200-token summary saves ~49K tokens/turn
/// </summary>
public sealed class LargeResultSavingTool : DelegatingAIFunction
{
    private readonly int _maxChars;
    private readonly int _previewChars;
    private readonly string _outputDir;
    private int _filesSaved;

    /// <param name="innerTool">The MCP tool (or any AIFunction) to wrap.</param>
    /// <param name="maxChars">Character threshold above which results are saved to file (~4 chars/token).</param>
    /// <param name="previewChars">How many characters to include in the summary preview.</param>
    /// <param name="outputDir">Directory where result files are saved.</param>
    public LargeResultSavingTool(
        AIFunction innerTool,
        int maxChars = 2000,
        int previewChars = 300,
        string? outputDir = null)
        : base(innerTool)
    {
        _maxChars = maxChars;
        _previewChars = previewChars;
        _outputDir = outputDir ?? Path.Combine(Directory.GetCurrentDirectory(), ".tool_results");
    }

    public int FilesSaved => _filesSaved;

    protected override async ValueTask<object?> InvokeCoreAsync(
        AIFunctionArguments arguments, CancellationToken cancellationToken)
    {
        var result = await base.InvokeCoreAsync(arguments, cancellationToken);

        // McpClientTool returns a JsonElement containing the CallToolResult
        if (result is not JsonElement je)
            return result;

        // Extract text content from the CallToolResult
        if (!je.TryGetProperty("content", out var contentArray) ||
            contentArray.ValueKind != JsonValueKind.Array)
            return result;

        var fullText = new StringBuilder();
        foreach (var item in contentArray.EnumerateArray())
        {
            if (item.TryGetProperty("text", out var textProp) &&
                textProp.ValueKind == JsonValueKind.String)
            {
                fullText.Append(textProp.GetString());
            }
        }

        if (fullText.Length <= _maxChars)
            return result;

        // Save to file
        Directory.CreateDirectory(_outputDir);
        var text = fullText.ToString();
        var hash = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(text)))[..12];
        var filename = $"{Name}_{hash}.txt";
        var filepath = Path.Combine(_outputDir, filename);

        await File.WriteAllTextAsync(filepath, text, cancellationToken);
        Interlocked.Increment(ref _filesSaved);

        var estimatedTokens = text.Length / 4;
        var preview = text.Length > _previewChars
            ? text[.._previewChars] + "..."
            : text;

        // Return a modified CallToolResult with the summary
        var summary = $"""
            [Large result saved to file]
            File: {filepath}
            Size: {text.Length:N0} chars (~{estimatedTokens:N0} tokens)
            Tool: {Name}

            Preview:
            {preview}
            """;

        // Build a new CallToolResult JSON with the summary
        return JsonSerializer.SerializeToElement(new
        {
            content = new[] { new { type = "text", text = summary } }
        });
    }

    /// <summary>
    /// Wrap all tools in a collection, applying save-to-file behavior to each.
    /// </summary>
    public static IList<AITool> WrapAll(
        IEnumerable<AITool> tools,
        int maxChars = 2000,
        int previewChars = 300,
        string? outputDir = null)
    {
        return tools.Select(t => t is AIFunction func
            ? (AITool)new LargeResultSavingTool(func, maxChars, previewChars, outputDir)
            : t).ToList();
    }
}
