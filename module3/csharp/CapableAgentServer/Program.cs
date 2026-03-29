using Anthropic;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using ModelContextProtocol.Client;
using ModelContextProtocol.Server;

// === MCP CONNECTION: meta-tools server ========================================

var apiUrl = Environment.GetEnvironmentVariable("MADEUPTASKS_API_URL") ?? "http://localhost:8090/api/v1";
var apiToken = Environment.GetEnvironmentVariable("MADEUPTASKS_API_TOKEN") ?? "tf_token_alice";

await using var mcpClient = await McpClient.CreateAsync(new StdioClientTransport(new()
{
    Name = "madeuptasks-meta",
    Command = "dotnet",
    Arguments = ["run", "--project", Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "..", "..", "module2", "csharp", "MetaToolsServer"))],
    EnvironmentVariables = new Dictionary<string, string?>
    {
        ["MADEUPTASKS_API_URL"] = apiUrl,
        ["MADEUPTASKS_API_TOKEN"] = apiToken,
    },
}));

var mcpTools = await mcpClient.ListToolsAsync();

// === MODEL ====================================================================

// AnthropicClient reads ANTHROPIC_API_KEY from environment by default
var client = new AnthropicClient();

// === AGENT ====================================================================

const string expertInstruction = """
    You are an expert project management assistant with deep knowledge of the
    MadeUpTasks platform API.  Your responses will be consumed by another AI agent,
    not directly by a human.

    Guidelines:
    - Be precise and structured.  Return data in a clear, parseable format.
    - Always use the available tools to retrieve real data -- never fabricate.
    - When navigating the API, start with list_endpoints to discover available
      resources, then describe_endpoint to understand parameters, then
      execute_endpoint to fetch data.
    - For multi-step requests, complete all steps before responding.
    - Include relevant IDs alongside names so the calling agent can take action.
    - If a request is ambiguous, make a reasonable interpretation and note your
      assumption in the response.
    - Keep responses concise -- no conversational filler.
    """;

AIAgent agent = client.AsAIAgent(
    model: "claude-opus-4-6",
    name: "MadeUpTasksExpert",
    description: "Expert project management assistant that can navigate the MadeUpTasks API to answer complex questions and perform multi-step workflows",
    instructions: expertInstruction,
    tools: [.. mcpTools.Cast<AITool>()]);

// === EXPOSE AS MCP SERVER =====================================================

McpServerTool tool = McpServerTool.Create(agent.AsAIFunction());

HostApplicationBuilder builder = Host.CreateEmptyApplicationBuilder(settings: null);
builder.Services
    .AddMcpServer()
    .WithStdioServerTransport()
    .WithTools([tool]);

await builder.Build().RunAsync();
