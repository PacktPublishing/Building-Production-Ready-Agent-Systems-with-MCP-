using Anthropic;
using Microsoft.Agents.AI.DevUI;
using Microsoft.Agents.AI.Hosting;
using Microsoft.Agents.AI.Hosting.OpenAI;
using Microsoft.Extensions.AI;
using ModelContextProtocol.Client;
using SaveToFile;

// === MCP SERVER ===============================================================
// Use the baseline server — it returns unfiltered 40+ field responses,
// which makes the save-to-file wrapper's effect very visible.

var apiUrl = Environment.GetEnvironmentVariable("MADEUPTASKS_API_URL") ?? "http://localhost:8090/api/v1";
var apiToken = Environment.GetEnvironmentVariable("MADEUPTASKS_API_TOKEN") ?? "tf_token_alice";

Console.WriteLine("Starting baseline MCP server...");

await using var mcpClient = await McpClient.CreateAsync(new StdioClientTransport(new()
{
    Name = "madeuptasks-baseline",
    Command = "dotnet",
    Arguments = ["run", "--project", Path.GetFullPath(
        Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "..", "..",
            "module1", "csharp", "BaselineServer"))],
    EnvironmentVariables = new Dictionary<string, string?>
    {
        ["MADEUPTASKS_API_URL"] = apiUrl,
        ["MADEUPTASKS_API_TOKEN"] = apiToken,
    },
}));

var mcpTools = await mcpClient.ListToolsAsync();
Console.WriteLine($"Connected to MCP server with {mcpTools.Count} tools.");

// Wrap all tools with save-to-file behavior
var wrappedTools = LargeResultSavingTool.WrapAll(
    mcpTools.Cast<AITool>(),
    maxChars: 2000,       // ~500 tokens — save anything larger
    previewChars: 400,
    outputDir: ".tool_results");

// === WEB APP ==================================================================

var builder = WebApplication.CreateBuilder(args);

var anthropicClient = new AnthropicClient();
builder.Services.AddChatClient(anthropicClient.AsIChatClient("claude-sonnet-4-6"));

// Agent WITH save-to-file wrapping — large results go to disk
builder.AddAIAgent("WithSaveToFile",
    "You are a helpful assistant for MadeUpTasks project management. " +
    "When tool results are saved to files, mention the file path and " +
    "summarize the key information from the preview.")
    .WithAITools([.. wrappedTools]);

// Agent WITHOUT wrapping — full payloads stay in context (for comparison)
builder.AddAIAgent("WithoutSaveToFile",
    "You are a helpful assistant for MadeUpTasks project management.")
    .WithAITools([.. mcpTools.Cast<AITool>()]);

builder.Services.AddOpenAIResponses();
builder.Services.AddOpenAIConversations();
builder.AddDevUI();

var app = builder.Build();

app.MapOpenAIResponses();
app.MapOpenAIConversations();
app.MapDevUI();

Console.WriteLine();
Console.WriteLine("Save-to-File Demo (Module 6)");
Console.WriteLine("DevUI available at: http://localhost:8086/devui");
Console.WriteLine();
Console.WriteLine("Compare the two agents in the DevUI:");
Console.WriteLine("  - WithSaveToFile:    Large results saved to .tool_results/");
Console.WriteLine("  - WithoutSaveToFile: Full payloads kept in context");
Console.WriteLine();
Console.WriteLine("Watch the token counts in the OTel traces to see the difference.");

app.Run("http://localhost:8086");
