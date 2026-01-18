"""OAuth client configuration for GitHub and Google."""

from authlib.integrations.starlette_client import OAuth

from app.core.config import get_settings

settings = get_settings()

# Initialize OAuth
oauth = OAuth()

# GitHub OAuth configuration
oauth.register(
    name="github",
    client_id=settings.github_client_id,
    client_secret=settings.github_client_secret,
    access_token_url="https://github.com/login/oauth/access_token",
    access_token_params=None,
    authorize_url="https://github.com/login/oauth/authorize",
    authorize_params=None,
    api_base_url="https://api.github.com/",
    client_kwargs={"scope": "user:email read:user"},
)

# Google OAuth configuration
oauth.register(
    name="google",
    client_id=settings.google_client_id,
    client_secret=settings.google_client_secret,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


def get_oauth_client(provider: str) -> OAuth:
    """Get OAuth client for the specified provider."""
    if provider not in ("github", "google"):
        raise ValueError(f"Unknown OAuth provider: {provider}")
    return oauth
