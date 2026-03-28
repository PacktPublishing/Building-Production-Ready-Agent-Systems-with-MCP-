using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.IdentityModel.Tokens;
using ModelContextProtocol.AspNetCore.Authentication;
using McpServer.TokenExchange.Services;
using McpServer.TokenExchange.Tools;
using System.Security.Claims;

var builder = WebApplication.CreateBuilder(args);

var serverUrl = "http://localhost:7072/";
var keycloakUrl = builder.Configuration.GetValue("KEYCLOAK_URL", "http://localhost:8080")!;
var keycloakRealm = builder.Configuration.GetValue("KEYCLOAK_REALM", "workshop")!;
var keycloakAuthority = $"{keycloakUrl}/realms/{keycloakRealm}";
var projectApiUrl = builder.Configuration.GetValue("PROJECT_API_URL", "http://localhost:3000")!;

builder.Services.AddAuthentication(options =>
{
    options.DefaultChallengeScheme = McpAuthenticationDefaults.AuthenticationScheme;
    options.DefaultAuthenticateScheme = JwtBearerDefaults.AuthenticationScheme;
})
.AddJwtBearer(options =>
{
    options.Authority = keycloakAuthority;
    options.RequireHttpsMetadata = false; // Keycloak runs on HTTP in dev
    options.TokenValidationParameters = new TokenValidationParameters
    {
        ValidateIssuer = true,
        ValidateAudience = true,
        ValidateLifetime = true,
        ValidateIssuerSigningKey = true,
        ValidAudience = "project-api",
        ValidIssuer = keycloakAuthority,
        NameClaimType = "preferred_username",
        RoleClaimType = "realm_access.roles"
    };

    options.Events = new JwtBearerEvents
    {
        OnTokenValidated = context =>
        {
            var name = context.Principal?.Identity?.Name ?? "unknown";
            var scopes = context.Principal?.FindFirstValue("scope") ?? "";
            Console.WriteLine($"Token validated for: {name} (scopes: {scopes})");
            return Task.CompletedTask;
        },
        OnAuthenticationFailed = context =>
        {
            Console.WriteLine($"Authentication failed: {context.Exception.Message}");
            return Task.CompletedTask;
        }
    };
})
.AddMcp(options =>
{
    options.ResourceMetadata = new()
    {
        ResourceDocumentation = "MadeUpTasks Project Manager - C# MCP Server (Token Exchange)",
        AuthorizationServers = { keycloakAuthority },
        ScopesSupported = ["tasks:read", "tasks:admin"],
    };
});

builder.Services.AddAuthorization();

builder.Services.AddHttpContextAccessor();

// Register the token exchange service
builder.Services.AddSingleton<ITokenExchangeService, KeycloakTokenExchangeService>();

builder.Services.AddMcpServer()
    .WithTools<TaskTools>()
    .WithHttpTransport();

// HttpClient for the downstream project-api
builder.Services.AddHttpClient("ProjectApi", client =>
{
    client.BaseAddress = new Uri(projectApiUrl);
});

var app = builder.Build();

app.UseAuthentication();
app.UseAuthorization();

app.MapMcp().RequireAuthorization();

Console.WriteLine($"Starting MCP server (Token Exchange) at {serverUrl}");
Console.WriteLine($"Keycloak authority: {keycloakAuthority}");
Console.WriteLine($"Project API: {projectApiUrl}");
Console.WriteLine("Token exchange: ENABLED — user tokens will be exchanged for project-api-scoped tokens");

app.Run(serverUrl);
