namespace McpServer.TokenExchange.Services;

public interface ITokenExchangeService
{
    /// <summary>
    /// Exchange a user's access token for a new token scoped to the target audience.
    /// Uses RFC 8693 (OAuth 2.0 Token Exchange) against Keycloak.
    /// </summary>
    Task<string> ExchangeTokenAsync(string subjectToken, CancellationToken cancellationToken = default);
}
