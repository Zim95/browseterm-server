'''
To understand the implementation, read the following articles:
- Github Login: https://medium.com/@tony.infisical/guide-to-using-oauth-2-0-to-access-github-api-818383862591
- Google Login: https://medium.com/@tony.infisical/guide-to-using-oauth-2-0-to-access-google-apis-dead94d6866d

AUTH_REDIRECT_BASE_URI: str = os.getenv("AUTH_REDIRECT_BASE_URI", "http://localhost:9999")

Google Configuration:
--------------------
GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_AUTH_META_URL: str = 'https://accounts.google.com/o/oauth2/auth'
GOOGLE_AUTH_SCOPE: str = 'openid email profile'
GOOGLE_AUTH_REDIRECT_URI: str = f"{AUTH_REDIRECT_BASE_URI}/google-login-redirect"
GOOGLE_ACCESS_TOKEN_URL: str = 'https://oauth2.googleapis.com/token'
GOOGLE_USER_INFO_URL: str = 'https://www.googleapis.com/oauth2/v2/userinfo'
GOOGLE_TOKEN_EXCHANGE_HEADERS: dict = {'Content-Type': 'application/x-www-form-urlencoded'}

Github Configuration:
---------------------
GITHUB_CLIENT_ID: str = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET: str = os.getenv("GITHUB_CLIENT_SECRET")
GITHUB_AUTH_META_URL: str = 'https://github.com/login/oauth/authorize'
GITHUB_AUTH_SCOPE: str = 'user:email user'
GITHUB_AUTH_REDIRECT_URI: str = f"{AUTH_REDIRECT_BASE_URI}/github-login-redirect"
GITHUB_ACCESS_TOKEN_URL: str = 'https://github.com/login/oauth/access_token'
GITHUB_USER_INFO_URL: str = 'https://api.github.com/user'
GITHUB_TOKEN_EXCHANGE_HEADERS: dict = {
    'Content-Type': 'application/x-www-form-urlencoded',
    'Accept': 'application/json',
    'Accept-Encoding': 'application/json'
}

Flow:
-----
1. User clicks the login button, this will redirect to <PROVIDER_NAME>_AUTH_META_URL with the following parameters:
    - client_id: <PROVIDER_NAME>_CLIENT_ID
    - redirect_uri: <PROVIDER_NAME>_AUTH_REDIRECT_URI
    - response_type: 'code'
    - scope: <PROVIDER_NAME>_AUTH_SCOPE (e.g. 'openid email profile' for Google)
    - state: CSRF token (generated on the frontend)

2. User is redirected to the Google or Github login page. User logs in there and hits allow.

3. User is then redirected to <PROVIDER_NAME>_AUTH_REDIRECT_URI with the following parameters:
    - code: authorization code
    - state: CSRF token (generated on the frontend)
    - NOTE: example, /google-login-redirect or /github-login-redirect
    - These are html pages. Here Front end validates the state and then redirects to <PROVIDER_NAME>_TOKEN_EXCHANGE_URI (example: /google-token-exchange or /github-token-exchange)

4. Backend receives a POST request with code and state. It does not need the state anymore, but uses code.
    - It exchanges the code for tokens with the following credentials:
        - client_id: <PROVIDER_NAME>_CLIENT_ID
        - client_secret: <PROVIDER_NAME>_CLIENT_SECRET
        - redirect_uri: <PROVIDER_NAME>_AUTH_REDIRECT_URI
        - access_token_url: <PROVIDER_NAME>_ACCESS_TOKEN_URI
    - It then fetches the user info with the access token using the following credentials:
        - user_info_url: <PROVIDER_NAME>_USER_INFO_URI
        - access_token: access token
    - Returns the user info.

5. But this user info is not returned. Actually a session is created with the user info and a session id is returned in a cookie.
    Once that happens, the user is redirected to the home page.

OAuth Authentication Flow Diagram:
==================================

┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   User Browser  │    │   BrowseTerm    │    │  OAuth Provider │    │     Redis       │
│                 │    │    Frontend     │    │ (Google/GitHub) │    │   (Sessions)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
         │                        │                        │                        │
         │ 1. Click Login Button  │                        │                        │
         ├───────────────────────►│                        │                        │
         │                        │                        │                        │
         │ 2. Redirect to OAuth   │                        │                        │
         │    with client_id,     │                        │                        │
         │    redirect_uri,       │                        │                        │
         │    scope, state        │                        │                        │
         ├─────────────────────────────────────────────────►│                        │
         │                        │                        │                        │
         │ 3. User Login &        │                        │                        │
         │    Authorization       │                        │                        │
         │◄─────────────────────────────────────────────────┤                        │
         │                        │                        │                        │
         │ 4. Redirect with       │                        │                        │
         │    authorization code  │                        │                        │
         │    & state             │                        │                        │
         ├───────────────────────►│                        │                        │
         │                        │                        │                        │
         │ 5. Validate state &    │                        │                        │
         │    POST to token       │                        │                        │
         │    exchange endpoint   │                        │                        │
         ├───────────────────────┼───────────────────────►│                        │
         │                        │                        │                        │
         │ 6. Exchange code for   │                        │                        │
         │    access token        │                        │                        │
         │◄───────────────────────┼───────────────────────┤                        │
         │                        │                        │                        │
         │ 7. Fetch user info     │                        │                        │
         │    with access token   │                        │                        │
         │◄───────────────────────┼───────────────────────┤                        │
         │                        │                        │                        │
         │ 8. Create session &    │                        │                        │
         │    store in Redis      │                        │                        │
         │                        ├───────────────────────┼───────────────────────►│
         │                        │                        │                        │
         │ 9. Set HTTP-only       │                        │                        │
         │    session cookie      │                        │                        │
         │◄───────────────────────┤                        │                        │
         │                        │                        │                        │
         │ 10. Return JSON with   │                        │                        │
         │     user info &        │                        │                        │
         │     success message    │                        │                        │
         │◄───────────────────────┤                        │                        │
         │                        │                        │                        │
         │ 11. Store user info    │                        │                        │
         │     in localStorage &  │                        │                        │
         │     redirect to home  │                        │                        │
         ├───────────────────────►│                        │                        │
         │                        │                        │                        │
         │ 12. Subsequent         │                        │                        │
         │     requests use       │                        │                        │
         │     session cookie     │                        │                        │
         ├───────────────────────┼───────────────────────┼───────────────────────►│
         │                        │                        │                        │
         │                        │ 13. Validate session   │                        │
         │                        │     & return user info│                        │
         │◄───────────────────────┼───────────────────────┼◄───────────────────────┤

Key Components:
- CSRF Protection: state parameter prevents cross-site request forgery
- Session Management: Redis stores user sessions for multi-pod scalability  
- HTTP-only Cookies: Prevents XSS attacks on session tokens
- Profile Data: Fetches username, email, and profile picture from OAuth provider
- Secure Redirects: Validates redirect URIs to prevent open redirect attacks
'''