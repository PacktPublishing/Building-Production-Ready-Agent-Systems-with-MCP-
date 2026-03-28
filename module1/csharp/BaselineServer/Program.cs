using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using BaselineServer;

var builder = Host.CreateApplicationBuilder(args);

builder.Services.AddHttpClient("MadeUpTasksApi", client =>
{
    var apiUrl = Environment.GetEnvironmentVariable("MADEUPTASKS_API_URL") ?? "http://localhost:8090/api/v1";
    var apiToken = Environment.GetEnvironmentVariable("MADEUPTASKS_API_TOKEN") ?? "tf_token_alice";
    client.BaseAddress = new Uri(apiUrl.TrimEnd('/') + "/");
    client.DefaultRequestHeaders.Add("Authorization", $"Bearer {apiToken}");
    client.Timeout = TimeSpan.FromSeconds(30);
});

builder.Services.AddMcpServer()
    .WithTools<BaselineTools>()
    .WithStdioServerTransport();

await builder.Build().RunAsync();
