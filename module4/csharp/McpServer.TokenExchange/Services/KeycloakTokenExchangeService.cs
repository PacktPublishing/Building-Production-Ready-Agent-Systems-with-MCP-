using System.Text.Json;

namespace McpServer.TokenExchange.Services;

public sealed class KeycloakTokenExchangeService : ITokenExchangeService
{
    private readonly IHttpClientFactory _httpClientFactory;
    private readonly ILogger<KeycloakTokenExchangeService> _logger;
    private readonly string _tokenEndpoint;
    private readonly string _clientId;
    private readonly string _clientSecret;
    private readonly string _targetAudience;

    // Agent identity — registered as a separate Keycloak client
    private readonly string _agentClientId;
    private readonly string _agentClientSecret;

    public KeycloakTokenExchangeService(
        IHttpClientFactory httpClientFactory,
        ILogger<KeycloakTokenExchangeService> logger,
        IConfiguration configuration)
    {
        _httpClientFactory = httpClientFactory;
        _logger = logger;

        var keycloakUrl = configuration.GetValue("KEYCLOAK_URL", "http://localhost:8080")!;
        var realm = configuration.GetValue("KEYCLOAK_REALM", "workshop")!;
        _tokenEndpoint = $"{keycloakUrl}/realms/{realm}/protocol/openid-connect/token";
        _clientId = configuration.GetValue("MCP_SERVER_CLIENT_ID", "mcp-server")!;
        _clientSecret = configuration.GetValue("MCP_SERVER_CLIENT_SECRET", "mcp-server-secret")!;
        _targetAudience = configuration.GetValue("TARGET_AUDIENCE", "project-api")!;
        _agentClientId = configuration.GetValue("AGENT_CLIENT_ID", "agent-baseline")!;
        _agentClientSecret = configuration.GetValue("AGENT_CLIENT_SECRET", "agent-baseline-secret")!;
    }

    // =========================================================================
    // Token Exchange — Three levels of identity
    //
    // Level 1 (default): Audience exchange only
    //   Token: { sub: "bob", azp: "mcp-server", aud: "project-api" }
    //   The API knows the user and the target, but not how the request arrived.
    //
    // Level 2: MCP server delegation (uncomment LEVEL_2 lines)
    //   Token: { sub: "bob", azp: "mcp-server", act: { sub: "service-account-mcp-server" } }
    //   The API can see that mcp-server is acting on bob's behalf.
    //
    // Level 3: Agent identity (uncomment LEVEL_3 lines instead of LEVEL_2)
    //   Token: { sub: "bob", azp: "mcp-server", act: { sub: "service-account-agent-baseline" } }
    //   The API can see that an AI agent is acting on bob's behalf.
    //   The MCP server identity (azp) is still present as the party that
    //   performed the exchange. The agent identity in "act" enables policies
    //   like "block agent access to this endpoint" — an emerging pattern for
    //   organizations that need to restrict which APIs agents can call.
    //
    //   To use: register each agent as a Keycloak client with
    //   serviceAccountsEnabled=true (see agent-baseline in realm-export.json).
    // =========================================================================

    public async Task<string> ExchangeTokenAsync(string subjectToken, CancellationToken cancellationToken = default)
    {
        _logger.LogInformation("Exchanging token for audience: {Audience}", _targetAudience);

        var client = _httpClientFactory.CreateClient();

        // --- LEVEL_2: Uncomment for MCP server as actor ---
        // var actorToken = await GetServiceAccountTokenAsync(
        //     client, _clientId, _clientSecret, cancellationToken);

        // --- LEVEL_3: Uncomment for AI agent as actor (use INSTEAD of LEVEL_2) ---
        // var actorToken = await GetServiceAccountTokenAsync(
        //     client, _agentClientId, _agentClientSecret, cancellationToken);

        var formParams = new Dictionary<string, string>
        {
            ["grant_type"] = "urn:ietf:params:oauth:grant-type:token-exchange",
            ["client_id"] = _clientId,
            ["client_secret"] = _clientSecret,
            ["subject_token"] = subjectToken,
            ["subject_token_type"] = "urn:ietf:params:oauth:token-type:access_token",
            ["requested_token_type"] = "urn:ietf:params:oauth:token-type:access_token",
            ["audience"] = _targetAudience,
        };

        // --- LEVEL_2 or LEVEL_3: Uncomment to include the actor token ---
        // formParams["actor_token"] = actorToken;
        // formParams["actor_token_type"] = "urn:ietf:params:oauth:token-type:access_token";

        var request = new HttpRequestMessage(HttpMethod.Post, _tokenEndpoint)
        {
            Content = new FormUrlEncodedContent(formParams)
        };

        var response = await client.SendAsync(request, cancellationToken);
        var body = await response.Content.ReadAsStringAsync(cancellationToken);

        if (!response.IsSuccessStatusCode)
        {
            _logger.LogError("Token exchange failed ({StatusCode}): {Body}", response.StatusCode, body);
            throw new InvalidOperationException(
                $"Token exchange failed: {response.StatusCode}. " +
                "Check that Keycloak has token-exchange enabled and permissions are configured. " +
                "Run setup-token-exchange.sh after Keycloak starts.");
        }

        using var doc = JsonDocument.Parse(body);
        var accessToken = doc.RootElement.GetProperty("access_token").GetString()
            ?? throw new InvalidOperationException("Token exchange response missing access_token.");

        _logger.LogInformation("Token exchange successful — new token issued for audience: {Audience}", _targetAudience);
        return accessToken;
    }

    /// <summary>
    /// Get a service account token for any Keycloak client via client_credentials grant.
    /// Used as the actor_token in the exchange to produce the "act" claim.
    /// </summary>
    private async Task<string> GetServiceAccountTokenAsync(
        HttpClient client, string clientId, string clientSecret, CancellationToken cancellationToken)
    {
        _logger.LogInformation("Getting service account token for: {ClientId}", clientId);

        var request = new HttpRequestMessage(HttpMethod.Post, _tokenEndpoint)
        {
            Content = new FormUrlEncodedContent(new Dictionary<string, string>
            {
                ["grant_type"] = "client_credentials",
                ["client_id"] = clientId,
                ["client_secret"] = clientSecret,
            })
        };

        var response = await client.SendAsync(request, cancellationToken);
        var body = await response.Content.ReadAsStringAsync(cancellationToken);

        if (!response.IsSuccessStatusCode)
        {
            _logger.LogError("Service account token request failed for {ClientId} ({StatusCode}): {Body}",
                clientId, response.StatusCode, body);
            throw new InvalidOperationException(
                $"Failed to get service account token for '{clientId}': {response.StatusCode}");
        }

        using var doc = JsonDocument.Parse(body);
        return doc.RootElement.GetProperty("access_token").GetString()
            ?? throw new InvalidOperationException("Service account token response missing access_token.");
    }
}
