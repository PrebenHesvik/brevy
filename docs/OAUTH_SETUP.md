# OAuth Setup Guide

This guide explains how to set up OAuth applications for GitHub and Google authentication in Brevy.

## GitHub OAuth Setup

1. **Go to GitHub Developer Settings**
   - Navigate to https://github.com/settings/developers
   - Click "OAuth Apps" in the sidebar
   - Click "New OAuth App"

2. **Register a new OAuth application**
   - **Application name**: `Brevy` (or `Brevy Local` for development)
   - **Homepage URL**: `http://localhost:5173` (for local dev)
   - **Authorization callback URL**: `http://localhost:8000/api/v1/auth/github/callback`
   - Click "Register application"

3. **Get your credentials**
   - Copy the **Client ID**
   - Click "Generate a new client secret"
   - Copy the **Client Secret** (you won't see it again!)

4. **Configure Brevy**
   Add to your `.env` file:
   ```env
   GITHUB_CLIENT_ID=your_client_id_here
   GITHUB_CLIENT_SECRET=your_client_secret_here
   ```

## Google OAuth Setup

1. **Go to Google Cloud Console**
   - Navigate to https://console.cloud.google.com/
   - Create a new project or select an existing one

2. **Enable the Google+ API** (if not already enabled)
   - Go to "APIs & Services" > "Library"
   - Search for "Google+ API" and enable it

3. **Configure OAuth Consent Screen**
   - Go to "APIs & Services" > "OAuth consent screen"
   - Choose "External" (for testing) or "Internal" (for G Suite)
   - Fill in the required fields:
     - **App name**: `Brevy`
     - **User support email**: Your email
     - **Developer contact email**: Your email
   - Add scopes: `email`, `profile`, `openid`
   - Add test users (if External and not verified)

4. **Create OAuth Credentials**
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth client ID"
   - **Application type**: Web application
   - **Name**: `Brevy Web Client`
   - **Authorized JavaScript origins**:
     - `http://localhost:5173`
     - `http://localhost:8000`
   - **Authorized redirect URIs**:
     - `http://localhost:8000/api/v1/auth/google/callback`
   - Click "Create"

5. **Get your credentials**
   - Copy the **Client ID**
   - Copy the **Client Secret**

6. **Configure Brevy**
   Add to your `.env` file:
   ```env
   GOOGLE_CLIENT_ID=your_client_id_here
   GOOGLE_CLIENT_SECRET=your_client_secret_here
   ```

## Testing OAuth Locally

1. **Start the services**
   ```bash
   make docker-up
   make db-upgrade
   make dev
   ```

2. **Test GitHub Login**
   - Open http://localhost:8000/api/v1/auth/github
   - You'll be redirected to GitHub
   - After authorization, you'll be redirected to the dashboard

3. **Test Google Login**
   - Open http://localhost:8000/api/v1/auth/google
   - You'll be redirected to Google
   - After authorization, you'll be redirected to the dashboard

4. **Check your user**
   - Open http://localhost:8000/api/v1/auth/me
   - You should see your user information

## Production Configuration

For production, update the following:

1. **Callback URLs** - Use your production domain:
   - GitHub: `https://yourdomain.com/api/v1/auth/github/callback`
   - Google: `https://yourdomain.com/api/v1/auth/google/callback`

2. **Security settings** in `app/api/v1/auth.py`:
   - Change `FRONTEND_URL` to your production frontend URL
   - Set `secure=True` for cookies (requires HTTPS)

3. **Session middleware** in `app/main.py`:
   - Set `https_only=True`

## Troubleshooting

### "Failed to authenticate with GitHub/Google"
- Check that your client ID and secret are correct
- Verify the callback URL matches exactly (including trailing slashes)
- Check the API logs for detailed error messages

### "Could not get email"
- For GitHub: User must have a public email or you need `user:email` scope
- For Google: Ensure `email` scope is included in consent screen

### "Email already registered with another provider"
- Users can only register with one OAuth provider
- To switch providers, the old account must be deleted first

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/auth/github` | GET | Initiate GitHub OAuth |
| `/api/v1/auth/github/callback` | GET | GitHub OAuth callback |
| `/api/v1/auth/google` | GET | Initiate Google OAuth |
| `/api/v1/auth/google/callback` | GET | Google OAuth callback |
| `/api/v1/auth/logout` | POST | Clear auth cookie |
| `/api/v1/auth/me` | GET | Get current user (requires auth) |
| `/api/v1/auth/status` | GET | Check auth status (no 401) |
