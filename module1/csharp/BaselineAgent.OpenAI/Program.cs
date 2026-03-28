using Microsoft.Agents.AI.DevUI;
using Microsoft.Agents.AI.Hosting;
using Microsoft.Agents.AI.Hosting.OpenAI;
using Microsoft.Extensions.AI;
using ModelContextProtocol.Client;
using OpenAI;

// === MCP SERVER ===============================================================

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

// The only difference from the Anthropic version: use OpenAIClient + ChatClient
// OpenAIClient reads OPENAI_API_KEY from environment by default
var openAiClient = new OpenAIClient(Environment.GetEnvironmentVariable("OPENAI_API_KEY"));
builder.Services.AddChatClient(openAiClient.GetChatClient("gpt-4.1").AsIChatClient());

builder.AddAIAgent("MadeUpTasksBaseline", "You are a helpful assistant for MadeUpTasks project management.")
    .WithAITools([.. mcpTools.Cast<AITool>()]);

builder.Services.AddOpenAIResponses();
builder.Services.AddOpenAIConversations();
builder.AddDevUI();

var app = builder.Build();

app.MapOpenAIResponses();
app.MapOpenAIConversations();
app.MapDevUI();

Console.WriteLine();
Console.WriteLine("MadeUpTasks Baseline Agent (C# + OpenAI)");
Console.WriteLine("DevUI available at: http://localhost:8084/devui");
Console.WriteLine();

app.Run("http://localhost:8084");
