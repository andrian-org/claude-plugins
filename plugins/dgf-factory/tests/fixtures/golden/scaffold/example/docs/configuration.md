# Configuration

Every value that is a secret, a host, a feed, a registry or an image is a `${VAR}` in the generated files, and is
declared once here and in [docker/.env.example](../docker/.env.example). A secret is marked, and has no example
value.

The hosts read them through `appsettings.json`, where each key holds its `${VAR}` as a placeholder, and through the
environment: the compose file sets the same key, spelled with a double underscore, from the variable.

- **${MSSQL_SA_PASSWORD}** (secret) — The SQL Server `sa` password of the local stack. (group: Local stack)
- **${MSSQL_DB}** — The database the stack creates and publishes into. (group: Local stack) Example: `Inspections`.
- **${MSSQL_PORT}** — The host port SQL Server listens on. (group: Local stack) Example: `1433`.
- **${DB_CONNECTION_STRING}** (secret) — The SQL connection string of the API hosts, for example Data Source=sqlserver;Initial Catalog=<MSSQL_DB>;User ID=sa;Password=<MSSQL_SA_PASSWORD>;TrustServerCertificate=True; (group: Local stack)
- **${REDIS_CONNECTION}** — The Redis endpoint of the API hosts' cache. (group: Local stack) Example: `redis:6379`.
- **${SEQ_URL}** — The Seq log server the hosts write to. (group: Local stack) Example: `http://seq`.
- **${DGF_DB_INIT_IMAGE}** — An image that publishes the framework's database baseline into the stack's database. DGF pins none: build one from the framework's database project. (group: Images and feeds)
- **${DGF_UI_IMAGE}** — The DGF UI image, served by nginx. DGF pins no tag: build one from the framework's UI source. (group: Images and feeds)
- **${NUGET_FEED_URL}** — The NuGet source that serves the DGF.API package. (group: Images and feeds)
- **${NUGET_FEED_TOKEN}** (secret) — The access token for that feed. (group: Images and feeds)
- **${TLS_CERT_DIR}** — A directory holding cert.pem and key.pem for the hosts below. The host sets its cookies secure-only, so the stack must serve HTTPS. (group: Local stack) Example: `./certs`.
- **${COOKIE_DOMAIN}** — The domain the session cookies are set on. (group: Local stack) Example: `.localtest.me`.
- **${RA_BASE_URL}** — The Registration Authority every DGF integration authenticates through. (group: Integrations)
- **${RA_CALLING_SERVICE}** — The calling service name presented to the Registration Authority. (group: Integrations)
- **${RA_CERTIFICATE_THUMBPRINT}** — The thumbprint of the certificate registered for this service. (group: Integrations)
- **${RA_PRIVATE_KEY}** (secret) — The private key that signs the token request. (group: Integrations)
- **${SIGN_BASE_URL}** — The signing service. (group: Integrations)
- **${SIGN_SERVICE}** — The service name the signing scope belongs to. (group: Integrations)
- **${SIGN_SCOPE}** — The scope requested for signing. (group: Integrations)
- **${NOTIFY_BASE_URL}** — The notification service. (group: Integrations)
- **${NOTIFY_SERVICE}** — The service name the notification scope belongs to. (group: Integrations)
- **${NOTIFY_SCOPE}** — The scope requested for notification. (group: Integrations)
- **${NOTIFY_SENDER_EMAIL}** — The sender address of the notifications the hosts send. (group: Integrations)
- **${ADMIN_USERNAME}** — The user name of the first administrator, seeded at first start. (group: Sign-in) Example: `admin`.
- **${ADMIN_PASSWORD}** (secret) — The password of the first administrator. (group: Sign-in)
- **${ADMIN_EMAIL}** — The e-mail address of the first administrator. (group: Sign-in)
- **${PUBLICAPI_LANDSPUBLIC_UI_HOST}** — The host name the LandsPublic UI is served on. (group: Deployment PublicApi / LandsPublic)
- **${PUBLICAPI_LANDSPUBLIC_API_HOST}** — The host name the LandsPublic API is served on. (group: Deployment PublicApi / LandsPublic)
- **${PUBLICAPI_LANDSPUBLIC_DGPASS_AUTHORITY}** — The DGPass authority (issuer) URL. (group: Deployment PublicApi / LandsPublic)
- **${PUBLICAPI_LANDSPUBLIC_DGPASS_CLIENT_ID}** — The client id registered with DGPass. (group: Deployment PublicApi / LandsPublic)
- **${PUBLICAPI_LANDSPUBLIC_DGPASS_CLIENT_SECRET}** (secret) — The client secret registered with DGPass. (group: Deployment PublicApi / LandsPublic)
- **${PUBLICAPI_DEEDSPUBLIC_UI_HOST}** — The host name the DeedsPublic UI is served on. (group: Deployment PublicApi / DeedsPublic)
- **${PUBLICAPI_DEEDSPUBLIC_API_HOST}** — The host name the DeedsPublic API is served on. (group: Deployment PublicApi / DeedsPublic)
- **${PUBLICAPI_DEEDSPUBLIC_DGPASS_AUTHORITY}** — The DGPass authority (issuer) URL. (group: Deployment PublicApi / DeedsPublic)
- **${PUBLICAPI_DEEDSPUBLIC_DGPASS_CLIENT_ID}** — The client id registered with DGPass. (group: Deployment PublicApi / DeedsPublic)
- **${PUBLICAPI_DEEDSPUBLIC_DGPASS_CLIENT_SECRET}** (secret) — The client secret registered with DGPass. (group: Deployment PublicApi / DeedsPublic)
- **${STAFFAPI_LANDSSTAFF_UI_HOST}** — The host name the LandsStaff UI is served on. (group: Deployment StaffApi / LandsStaff)
- **${STAFFAPI_LANDSSTAFF_API_HOST}** — The host name the LandsStaff API is served on. (group: Deployment StaffApi / LandsStaff)
- **${STAFFAPI_LANDSSTAFF_AZURE_AUTHORITY}** — The Azure AD authority URL, without the tenant. (group: Deployment StaffApi / LandsStaff)
- **${STAFFAPI_LANDSSTAFF_AZURE_TENANT_ID}** — The Azure AD tenant id. (group: Deployment StaffApi / LandsStaff)
- **${STAFFAPI_LANDSSTAFF_AZURE_CLIENT_ID}** — The application (client) id. (group: Deployment StaffApi / LandsStaff)
- **${STAFFAPI_LANDSSTAFF_AZURE_CLIENT_SECRET}** (secret) — The client secret. (group: Deployment StaffApi / LandsStaff)
- **${STAFFAPI_DEEDSSTAFF_UI_HOST}** — The host name the DeedsStaff UI is served on. (group: Deployment StaffApi / DeedsStaff)
- **${STAFFAPI_DEEDSSTAFF_API_HOST}** — The host name the DeedsStaff API is served on. (group: Deployment StaffApi / DeedsStaff)
- **${STAFFAPI_DEEDSSTAFF_AZURE_AUTHORITY}** — The Azure AD authority URL, without the tenant. (group: Deployment StaffApi / DeedsStaff)
- **${STAFFAPI_DEEDSSTAFF_AZURE_TENANT_ID}** — The Azure AD tenant id. (group: Deployment StaffApi / DeedsStaff)
- **${STAFFAPI_DEEDSSTAFF_AZURE_CLIENT_ID}** — The application (client) id. (group: Deployment StaffApi / DeedsStaff)
- **${STAFFAPI_DEEDSSTAFF_AZURE_CLIENT_SECRET}** (secret) — The client secret. (group: Deployment StaffApi / DeedsStaff)
