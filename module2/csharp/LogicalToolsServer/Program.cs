using LogicalToolsServer.Services;
using LogicalToolsServer.Tools;
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

builder.Services.AddSingleton<ApiClient>();
builder.Services.AddSingleton<StatusHelper>();
builder.Services.AddSingleton<UserResolver>();

builder.Services.AddMcpServer()
    .WithTools<LogicalTools>()
    .WithStdioServerTransport();

await builder.Build().RunAsync();
