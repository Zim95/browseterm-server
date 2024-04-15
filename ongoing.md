1. So we are dropping Sessions.
2. We will be redirecting to front end with access tokens.
3. But token storage will not happen securely, we will have to store access tokens using javascript.
4. Because, we cannot set cookie for localhost:8001
4. This means we will be vulnerable to XSS. Because if anything is set by JS it can be accessed by JS.


Video:
1. Setup backend with nodemon- upto 15:19
2. Setup database - 20:50
3. Setup basic routing and design Front end - 32:00
4. Design Login Screen - 35:21
5. DB Schema setup - 39:00
6. Setup Google Console and Get Client ID and Secret - 50:31
7. Setup session (Watch this imp) - 57:30
8. 