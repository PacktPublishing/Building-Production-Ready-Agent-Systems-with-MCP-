using Anthropic;
using Microsoft.Agents.AI.DevUI;
using Microsoft.Agents.AI.Hosting;
using Microsoft.Agents.AI.Hosting.OpenAI;
using Microsoft.Extensions.AI;
using ModelContextProtocol.Client;

// === MCP SERVER ===============================================================
// Connects to the baseline MCP server — raw API passthrough, no shaping.

var apiUrl = Environment.GetEnvironmentVariable("MADEUPTASKS_API_URL") ?? "http://localhost:8090/api/v1";
var apiToken = Environment.GetEnvironmentVariable("MADEUPTASKS_API_TOKEN") ?? "tf_token_alice";

Console.WriteLine("Starting baseline MCP server...");

await using var mcpClient = await McpClient.CreateAsync(new StdioClientTransport(new()
{
    Name = "madeuptasks-baseline",
    Command = "dotnet",
    Arguments = ["run", "--project", Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "BaselineServer"))],
    EnvironmentVariables = new Dictionary<string, string?>
    {
        ["MADEUPTASKS_API_URL"] = apiUrl,
        ["MADEUPTASKS_API_TOKEN"] = apiToken,
    },
}));

var mcpTools = await mcpClient.ListToolsAsync();
Console.WriteLine($"Connected to MCP server with {mcpTools.Count} tools.");

// === WEB APP ==================================================================

var builder = WebApplication.CreateBuilder(args);

// Register Anthropic as the chat client
var anthropicClient = new AnthropicClient();
builder.Services.AddChatClient(anthropicClient.AsIChatClient("claude-sonnet-4-6"));

// Register the baseline agent with MCP tools
builder.AddAIAgent("MadeUpTasksBaseline", "You are a helpful assistant for MadeUpTasks project management.")
    .WithAITools([.. mcpTools.Cast<AITool>()]);

// DevUI services
builder.Services.AddOpenAIResponses();
builder.Services.AddOpenAIConversations();
builder.AddDevUI();

var app = builder.Build();

// Map endpoints
app.MapOpenAIResponses();
app.MapOpenAIConversations();
app.MapDevUI();

Console.WriteLine();
Console.WriteLine("MadeUpTasks Baseline Agent (C#)");
Console.WriteLine("DevUI available at: http://localhost:8084/devui");
Console.WriteLine();

app.Run("http://localhost:8084");
