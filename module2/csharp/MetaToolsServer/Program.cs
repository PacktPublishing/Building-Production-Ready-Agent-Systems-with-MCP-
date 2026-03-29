using MetaToolsServer.Services;
using MetaToolsServer.Tools;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;

var builder = Host.CreateApplicationBuilder(args);

builder.Services.AddHttpClient("MadeUpTasksApi", client =>
{
    var apiUrl = Environment.GetEnvironmentVariable("MADEUPTASKS_API_URL") ?? "http://localhost:8090/api/v1";
    var apiToken = Environment.GetEnvironmentVariable("MADEUPTASKS_API_TOKEN") ?? "tf_token_alice";
    client.BaseAddress = new Uri(apiUrl.TrimEnd('/') + "/");
    client.DefaultRequestHeaders.Add("Authorization", $"Bearer {apiToken}");
    client.Timeout = TimeSpan.FromSeconds(30);
});

builder.Services.AddSingleton<EndpointManifest>();

builder.Services.AddMcpServer(options =>
{
    options.ServerInfo = new() { Name = "madeuptasks-meta", Version = "1.0.0" };
    options.ServerInstructions = """
        This server exposes the MadeUpTasks API through four progressive-disclosure tools.

        Recommended workflow:
        1. Call ListEndpoints() with no arguments to see available API groups.
        2. Call ListEndpoints(group=...) to see endpoints in a group.
        3. Call DescribeEndpoint(method, path) to get full details for one endpoint.
        4. Call ExecuteEndpoint(method, path, ...) to call the API.

        You can also use SearchEndpoints(query) to find endpoints by keyword.
        Always call DescribeEndpoint before ExecuteEndpoint so you know the
        expected parameters and request body format.
        """;
})
.WithTools<MetaTools>()
.WithStdioServerTransport();

await builder.Build().RunAsync();
