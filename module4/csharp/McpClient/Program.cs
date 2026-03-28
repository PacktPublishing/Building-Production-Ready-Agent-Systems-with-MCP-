using Microsoft.Extensions.Logging;
using ModelContextProtocol.Client;
using ModelContextProtocol.Protocol;
using System.Diagnostics;
using System.Net;
using System.Text;
using System.Web;

var mcpServerUrl = "http://localhost:7071/";

Console.WriteLine("MadeUpTasks - Protected MCP Client (C#)");
Console.WriteLine($"Connecting to MCP server at {mcpServerUrl}...");
Console.WriteLine("This will open your browser for Keycloak login.");
Console.WriteLine();

var sharedHandler = new SocketsHttpHandler
{
    PooledConnectionLifetime = TimeSpan.FromMinutes(2),
    PooledConnectionIdleTimeout = TimeSpan.FromMinutes(1)
};
var httpClient = new HttpClient(sharedHandler);

var loggerFactory = LoggerFactory.Create(builder =>
{
    builder.AddConsole();
    builder.SetMinimumLevel(LogLevel.Information);
});

var transport = new HttpClientTransport(new()
{
    Endpoint = new Uri(mcpServerUrl),
    Name = "MadeUpTasks Client",
    OAuth = new()
    {
        ClientId = "mcp-client",
        RedirectUri = new Uri("http://localhost:1179/callback"),
        Scopes = ["openid", "tasks:read", "tasks:admin"],
        AuthorizationRedirectDelegate = HandleAuthorizationUrlAsync,
    }
}, httpClient, loggerFactory);

var client = await McpClient.CreateAsync(transport, loggerFactory: loggerFactory);

Console.WriteLine("Connected! Listing available tools...");
Console.WriteLine();

var tools = await client.ListToolsAsync();
if (tools.Count == 0)
{
    Console.WriteLine("No tools available on the server.");
    return;
}

Console.WriteLine($"Found {tools.Count} tool(s):");
foreach (var tool in tools)
{
    Console.WriteLine($"  - {tool.Name}: {tool.Description}");
}
Console.WriteLine();

// Demo: call list_tasks
if (tools.Any(t => t.Name == "ListTasks"))
{
    Console.WriteLine("--- Calling ListTasks ---");
    var result = await client.CallToolAsync("ListTasks", new Dictionary<string, object?>());
    Console.WriteLine(((TextContentBlock)result.Content[0]).Text);
    Console.WriteLine();
}

// Demo: call get_task
if (tools.Any(t => t.Name == "GetTask"))
{
    Console.WriteLine("--- Calling GetTask(TASK-001) ---");
    var result = await client.CallToolAsync("GetTask", new Dictionary<string, object?> { { "taskId", "TASK-001" } });
    Console.WriteLine(((TextContentBlock)result.Content[0]).Text);
    Console.WriteLine();
}

Console.WriteLine("Done! Press any key to exit.");
Console.ReadKey();

// ---------------------------------------------------------------------------
// OAuth browser-based authorization flow
// ---------------------------------------------------------------------------

static async Task<string?> HandleAuthorizationUrlAsync(
    Uri authorizationUrl, Uri redirectUri, CancellationToken cancellationToken)
{
    Console.WriteLine();
    Console.WriteLine("Starting OAuth authorization flow via Keycloak...");
    Console.WriteLine($"Opening browser to: {authorizationUrl}");
    Console.WriteLine();
    Console.WriteLine("Log in with one of these users:");
    Console.WriteLine("  alice / alice  (viewer - can list/get tasks)");
    Console.WriteLine("  bob   / bob    (admin  - can also create/close tasks)");
    Console.WriteLine();

    var listenerPrefix = redirectUri.GetLeftPart(UriPartial.Authority);
    if (!listenerPrefix.EndsWith("/")) listenerPrefix += "/";

    using var listener = new HttpListener();
    listener.Prefixes.Add(listenerPrefix);

    try
    {
        listener.Start();

        // Open the Keycloak login page in the default browser
        try
        {
            Process.Start(new ProcessStartInfo
            {
                FileName = authorizationUrl.ToString(),
                UseShellExecute = true
            });
        }
        catch
        {
            Console.WriteLine($"Could not open browser automatically.");
            Console.WriteLine($"Please open this URL manually: {authorizationUrl}");
        }

        var context = await listener.GetContextAsync();
        var query = HttpUtility.ParseQueryString(context.Request.Url?.Query ?? string.Empty);
        var code = query["code"];
        var error = query["error"];

        // Send a nice response back to the browser
        var responseHtml = """
            <html><body style="font-family: sans-serif; text-align: center; padding: 50px;">
            <h1>Authentication complete!</h1>
            <p>You can close this window and return to the terminal.</p>
            </body></html>
            """;
        byte[] buffer = Encoding.UTF8.GetBytes(responseHtml);
        context.Response.ContentLength64 = buffer.Length;
        context.Response.ContentType = "text/html";
        context.Response.OutputStream.Write(buffer, 0, buffer.Length);
        context.Response.Close();

        if (!string.IsNullOrEmpty(error))
        {
            Console.WriteLine($"Authentication error: {error}");
            return null;
        }

        if (string.IsNullOrEmpty(code))
        {
            Console.WriteLine("No authorization code received.");
            return null;
        }

        Console.WriteLine("Authorization code received successfully!");
        return code;
    }
    catch (Exception ex)
    {
        Console.WriteLine($"Error during OAuth flow: {ex.Message}");
        return null;
    }
    finally
    {
        if (listener.IsListening) listener.Stop();
    }
}
