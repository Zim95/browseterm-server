Login flow
==========
1. User will have to login using github or google. This will set session and insert user.
2. When logging into google or github, capture the route: by default it will be empty. This info will be stored in frontend localstorage.
3. Once logged in, user will be redirected to the route stored in localstorage.
4. Every, 25 minutes, a request will be sent to extend the session lifetime by 30 minutes.

Logout mechanism
5. If there is any unauthorized request, user will be logged out.
6. Every route switch will call: /@me route to get info, or get logged out. This is done through the protected route.