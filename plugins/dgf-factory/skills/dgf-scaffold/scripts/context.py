"""context.py — the template context: a resolved design, plus everything derived from it (ADR 0027 §7.3).

A template never computes: names, SQL types, application ids, host variables and the list of
`${VAR}` declarations are all decided here, from the design and the knowledge tables, so a
generated file says what the design says and two generated files never disagree. Imported by
generate.py; stdlib only.
"""

import uuid

BUILT_IN_ROLES = ("Administrators", "Members", "Anonymous", "Registered Users", "PortalUser")
ADMIN_ROLE = "Administrators"
MAX_SIZE = 2147483647
UIMASK = "001111"  # required for form, valid for grid and form, allow create — the samples' pattern
PORT = 4000  # the port DGF's host image listens on


def application_id(app_name, instance_name):
    """A re-generation from the same design reproduces the id (D3)."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"dgf-scaffold:{app_name}/{instance_name}")).upper()


def sql_type(field, rows):
    """A field's column type from the field-sql-types rows (the knowledge base), or None."""
    row = rows.get(field["dbtype"])
    if row is None:
        return None
    rule, text = row["Size rule"], row["SQL type"]
    if rule == "size":
        size = field["size"]
        return text.replace("(size)", "(MAX)" if size in ("MAX", MAX_SIZE) else f"({size})")
    if rule == "precision":
        precision = field.get("precision") if field.get("precision") is not None else 18
        scale = field.get("scale") if field.get("scale") is not None else 2
        return f"{text.split('(')[0]}({precision},{scale})"
    return text


def var(name, description, secret=False, example="", group="Local stack"):
    return {"name": name, "ref": "${" + name + "}", "description": description, "secret": secret,
            "example": example, "group": group}


def entity_context(entity, sql_rows, multi):
    fields = []
    for position, field in enumerate(entity["fields"]):
        is_key = field["name"] == entity["key"]
        size = field["size"]
        fields.append({
            **field,
            "is_key": is_key,
            "identity": is_key,
            "nullable": not field["required"] and not is_key,
            "sql_type": sql_type(field, sql_rows),
            "sql_null": "NOT NULL" if (field["required"] or is_key) else "NULL",
            "sql_identity": " IDENTITY (1, 1)" if is_key else "",
            "size_attr": "" if size is None else str(size),
            "has_size": size is not None,
            "readonly": "true" if is_key else "false",
            "required_attr": "true" if (field["required"] or is_key) else "false",
            "uimask": UIMASK,
            "has_extract": field["extract"] is not None,
            "extract_entity": field["extract"]["entity"] if field["extract"] else "",
            "extract_view": field["extract"]["view"] if field["extract"] else "",
            "ordinal": position,
        })
    key_field = next(f for f in fields if f["is_key"])
    display = next((f for f in fields if f["type"] == "Text" and not f["is_key"]
                    and f["dbtype"] in ("String", "StringUnicode")), None)
    return {
        "name": entity["name"], "title": entity["title"], "key": entity["key"], "key_dbtype": key_field["dbtype"],
        "fields": fields, "display_field": display["name"] if display else "",
        "display_title": display["title"] if display else "",
        "column_count": len(fields) + (1 if multi else 0),
        "has_application_id": multi,
    }


def build(design, sql_rows):
    """The whole context for one design; `design` is design.py's resolved dict and must be complete."""
    app = design["application"]
    instances_in = design["instances"]
    multi = len(instances_in) > 1
    model = design["instance_model"]
    shared = model == "shared-workspace"
    supply = design["base"]["supply"]
    by_instance = {}

    instances = []
    for index, item in enumerate(instances_in):
        directory = design["workspace"] if shared else item["name"]
        info = {
            "name": item["name"], "title": item["title"], "index": index, "number": index + 1,
            "workspace": directory, "application_id": application_id(app["name"], item["name"]),
            "short_name": item["name"].upper(), "mount": f"/workspaces/{item['name']}",
            "sitemap": f"_application-{item['name']}.sitemap",
        }
        instances.append(info)
        by_instance[item["name"]] = info

    if shared:
        workspaces = [{"dir": design["workspace"], "title": app["title"], "instances": instances, "shared": True,
                       "index": 0, "first": True}]
    else:
        workspaces = [{"dir": i["name"], "title": i["title"], "instances": [i], "shared": False,
                       "index": n, "first": n == 0} for n, i in enumerate(instances)]

    entities = [entity_context(e, sql_rows, multi) for e in design["data_model"]["entities"]]
    by_entity = {e["name"]: e for e in entities}
    for entity in entities:
        for field in entity["fields"]:
            field["extract_key"] = by_entity[field["extract_entity"]]["key"] if field["has_extract"] else ''

    # the roles of the database: the built-ins, then the design's, once each (the role index is on the name alone)
    seen, roles_all = set(), []
    for name in list(BUILT_IN_ROLES) + list(design["roles"]):
        if name.casefold() in seen:
            continue
        seen.add(name.casefold())
        roles_all.append({"name": name, "normalized": name.upper(), "builtin": name in BUILT_IN_ROLES})

    modules = []
    for module in design["modules"]:
        roles = module["roles"] or ["Members"]
        modules.append({
            **module,
            "roles": roles,
            "role_list": ",".join(roles),
            "entity_obj": by_entity.get(module["entity"]),
            "has_entity": module["entity"] is not None,
            "is_register": module["pattern"] == "register",
            "is_service": module["pattern"] == "service",
            "is_page": module["pattern"] == "page",
            "page": f"SiteMap/{module['name']}",
            "path": module["route"],
            "slug": module["name"].lower(),
        })
    has_process = any(m["is_service"] for m in modules)

    apis, deployments = [], []
    for api_index, api in enumerate(design["apis"]):
        items = []
        for dep in api["deployments"]:
            inst = by_instance[dep["instance"]]
            pfx = f"{api['name']}_{dep['name']}".upper()
            item = {
                "name": dep["name"], "api": api["name"], "api_index": api_index, "instance": dep["instance"],
                "instance_title": inst["title"], "workspace": inst["workspace"],
                "application_id": inst["application_id"], "auth": dep["auth"],
                "has_dgpass": "dgpass" in dep["auth"], "has_azure": "azure" in dep["auth"],
                "has_basic": "basic" in dep["auth"], "methods": [
                    {"name": m, "title": {"basic": "Sign in", "dgpass": "Sign in with DGPass",
                                          "azure": "Sign in with Microsoft"}[m], "first": n == 0}
                    for n, m in enumerate(dep["auth"])],
                "id": f"{api['name']}-{dep['name']}".lower(), "ui_id": f"{api['name']}-{dep['name']}-ui".lower(),
                "pfx": pfx, "settings_file": f"appsettings.{dep['name']}.json",
                "cookie_prefix": f"{dep['name']}".lower(),
                "api_dir": f"src/{api['name']}", "api_project": f"{api['name']}.csproj",
                "overlay": shared, "sitemap_file": inst["sitemap"],
                "ref": {name: "${" + f"{pfx}_{name.upper()}" + "}" for name in (
                    "ui_host", "api_host", "dgpass_authority", "dgpass_client_id", "dgpass_client_secret",
                    "azure_authority", "azure_tenant_id", "azure_client_id", "azure_client_secret")},
            }
            items.append(item)
            deployments.append(item)
        apis.append({"name": api["name"], "project": f"{api['name']}.csproj", "dir": f"src/{api['name']}",
                     "deployments": items, "index": api_index})

    first_workspace_dir = workspaces[0]["dir"]
    any_basic = any(d["has_basic"] for d in deployments)
    variables = variable_list(app, deployments, supply, any_basic)
    for dep in deployments:
        dep["env"] = common_env(any_basic) + deployment_env(dep)

    ctx = {
        "app": {"name": app["name"], "title": app["title"], "slug": app["name"].lower(),
                "dbprefix": app["name"].upper()},
        "dgf_version": design["dgf_version"],
        "model": model, "shared": shared, "multi": multi, "supply": supply,
        "supply_copy": supply == "copy", "supply_mount": supply == "mount",
        "instances": instances, "workspaces": workspaces, "first_workspace": first_workspace_dir,
        "first_instance": instances[0],
        "entities": entities, "has_entities": bool(entities), "modules": modules, "has_process": has_process,
        "register_modules": [m for m in modules if m["has_entity"]],
        "page_modules": [m for m in modules if m["is_page"]],
        "service_modules": [m for m in modules if m["is_service"]],
        "roles": roles_all, "design_roles": list(design["roles"]), "admin_role": ADMIN_ROLE,
        "apis": apis, "deployments": deployments, "any_basic": any_basic,
        "database": {"project": f"{app['name']}.Database", "dir": f"database/{app['name']}.Database"},
        "port": PORT,
        "vars": variables,
        "secret_vars": [v for v in variables if v["secret"]],
    }
    add_workspace_values(ctx)
    return ctx


# --- the workspace half: what the workspace templates read ---------------------------------------------

SIGN_IN_TITLES = {"basic": "Sign in", "dgpass": "Sign in with DGPass", "azure": "Sign in with Microsoft"}
COLUMN_TYPES = {  # a field's type -> (DataTable displayType, format, displayProperty)
    "Text": ("text", "", ""), "Html": ("text", "", ""), "Integer": ("number", "", ""),
    "Float": ("number", "n2", ""), "Money": ("number", "n2", ""), "Boolean": ("boolean", "yesNo", ""),
    "DateTime": ("dateTime", "dd MMM yyyy HH:mm", ""), "Lookup": ("text", "", "value"),
    "Picklist": ("text", "", "value"),
}
MEMBERS = "Members"


def profile_groups(modules):
    """[{name, title, modules}] — `Members` first, always; then one group per role a module narrows to.

    A group folder is named by its role exactly (the runtime splits `roles` on `,`, untrimmed), and a
    module is listed in every group its roles name; `Members` lists the modules open to any signed-in user.
    Only a module with an entity has a node (a legacy grid on the entity's default view); a `page` module
    is reached by its route alone.
    """
    groups = {MEMBERS.casefold(): {"name": MEMBERS, "title": MEMBERS, "modules": []}}
    for module in modules:
        if not module["has_entity"]:
            continue
        for role in module["roles"]:
            group = groups.setdefault(role.casefold(), {"name": role, "title": role, "modules": []})
            group["modules"].append(module)
    return list(groups.values())


def add_workspace_values(ctx):
    """Derived values for the workspace templates: sign-in methods per workspace, navigation, columns."""
    for workspace in ctx["workspaces"]:
        served = {i["name"] for i in workspace["instances"]}
        methods, seen = [], set()
        for dep in ctx["deployments"]:
            if dep["instance"] not in served:
                continue
            for name in dep["auth"]:
                if name not in seen:
                    seen.add(name)
                    methods.append({"name": name, "title": SIGN_IN_TITLES[name]})
        workspace["methods"] = methods
        workspace["method_count"] = len(methods)
        # the shell starts a DGPass login from the id `signIn` when the login route lists 0 or 1 methods
        workspace["multi_method"] = len(methods) > 1
    for module in ctx["modules"]:
        module["nav_path"] = module["route"].lstrip("/")
        module["route_name"] = f"mod{module['name']}Route"
    ctx["profile_groups"] = profile_groups(ctx["modules"])
    ctx["memberships"] = [{"name": f"{g['name']}/{m['name']}", "group": g, "module": m}
                          for g in ctx["profile_groups"] for m in g["modules"]]
    for entity in ctx["entities"]:
        for field in entity["fields"]:
            kind, fmt, prop = COLUMN_TYPES.get(field["type"], ("text", "", ""))
            field.update({"col_type": kind, "col_format": fmt, "col_property": prop,
                          "format_attr": "datetime" if field["type"] == "DateTime" else ""})


def common_env(any_basic):
    """The settings every deployment sets from ${VAR}s: the same keys appsettings.json holds as placeholders."""
    pairs = [
        ("ConnectionStrings__LocalSqlServer", "${DB_CONNECTION_STRING}"),
        ("ConnectionStrings__Redis", "${REDIS_CONNECTION}"),
        ("DistributedCachingOptions__RedisConnectionString", "${REDIS_CONNECTION}"),
        ("Authentication__SessionOptions__CookieDomain", "${COOKIE_DOMAIN}"),
        ("Integrations__RegistrationAuthority__BaseUrl", "${RA_BASE_URL}"),
        ("Integrations__RegistrationAuthority__TokenGeneration__CallingServiceFqn", "${RA_CALLING_SERVICE}"),
        ("Integrations__RegistrationAuthority__TokenGeneration__CertificateThumbprint", "${RA_CERTIFICATE_THUMBPRINT}"),
        ("Integrations__RegistrationAuthority__TokenGeneration__PrivateKey", "${RA_PRIVATE_KEY}"),
        ("Integrations__DgSign__BaseUrl", "${SIGN_BASE_URL}"),
        ("Integrations__DgSign__ApplicationScopes__Services__0", "${SIGN_SERVICE}"),
        ("Integrations__DgSign__ApplicationScopes__Scopes__0", "${SIGN_SCOPE}"),
        ("Integrations__DgNotify__BaseUrl", "${NOTIFY_BASE_URL}"),
        ("Integrations__DgNotify__ApplicationScopes__Services__0", "${NOTIFY_SERVICE}"),
        ("Integrations__DgNotify__ApplicationScopes__Scopes__0", "${NOTIFY_SCOPE}"),
        ("Integrations__DgNotify__SenderEmail", "${NOTIFY_SENDER_EMAIL}"),
        ("Integrations__DgNotifyOtp__BaseUrl", "${NOTIFY_BASE_URL}"),
        ("Integrations__DgNotifyOtp__ApplicationScopes__Services__0", "${NOTIFY_SERVICE}"),
        ("Integrations__DgNotifyOtp__ApplicationScopes__Scopes__0", "${NOTIFY_SCOPE}"),
        ("Serilog__WriteTo__1__Args__serverUrl", "${SEQ_URL}"),
    ]
    if any_basic:
        pairs += [("AdminSeedOptions__Accounts__0__Username", "${ADMIN_USERNAME}"),
                  ("AdminSeedOptions__Accounts__0__Password", "${ADMIN_PASSWORD}"),
                  ("AdminSeedOptions__Accounts__0__Email", "${ADMIN_EMAIL}")]
    return [{"key": k, "value": v, "secret": False} for k, v in pairs]


def deployment_env(dep):
    """The settings a deployment's compose service sets, as (config key with `__`, ${VAR}) pairs."""
    pfx = dep["pfx"]
    env = [
        ("WebAppHost", "https://${" + pfx + "_UI_HOST}", False),
        ("ReverseProxyHost", "https://${" + pfx + "_API_HOST}", False),
        ("CorsOrigins__0", "https://${" + pfx + "_UI_HOST}", False),
    ]
    if dep["has_dgpass"]:
        env += [("Authentication__DGPassOIDC__Authority", "${" + pfx + "_DGPASS_AUTHORITY}", False),
                ("Authentication__DGPassOIDC__ClientId", "${" + pfx + "_DGPASS_CLIENT_ID}", False),
                ("Authentication__DGPassOIDC__ClientSecret", "${" + pfx + "_DGPASS_CLIENT_SECRET}", True)]
    if dep["has_azure"]:
        env += [("Authentication__AzureOIDC__Authority", "${" + pfx + "_AZURE_AUTHORITY}", False),
                ("Authentication__AzureOIDC__TenantId", "${" + pfx + "_AZURE_TENANT_ID}", False),
                ("Authentication__AzureOIDC__ClientId", "${" + pfx + "_AZURE_CLIENT_ID}", False),
                ("Authentication__AzureOIDC__ClientSecret", "${" + pfx + "_AZURE_CLIENT_SECRET}", True)]
    return [{"key": k, "value": v, "secret": s} for k, v, s in env]


def variable_list(app, deployments, supply, any_basic):
    """Every `${VAR}` the generated files use, once — .env.example and configuration.md are rendered from it."""
    v = [
        var("MSSQL_SA_PASSWORD", "The SQL Server `sa` password of the local stack.", True),
        var("MSSQL_DB", "The database the stack creates and publishes into.", example=app["name"]),
        var("MSSQL_PORT", "The host port SQL Server listens on.", example="1433"),
        var("DB_CONNECTION_STRING", "The SQL connection string of the API hosts, for example "
            "Data Source=sqlserver;Initial Catalog=<MSSQL_DB>;User ID=sa;Password=<MSSQL_SA_PASSWORD>;"
            "TrustServerCertificate=True;", True),
        var("REDIS_CONNECTION", "The Redis endpoint of the API hosts' cache.", example="redis:6379"),
        var("SEQ_URL", "The Seq log server the hosts write to.", example="http://seq"),
        var("DGF_DB_INIT_IMAGE", "An image that publishes the framework's database baseline into the stack's "
            "database. DGF pins none: build one from the framework's database project.", group="Images and feeds"),
        var("DGF_UI_IMAGE", "The DGF UI image, served by nginx. DGF pins no tag: build one from the framework's UI "
            "source.", group="Images and feeds"),
        var("NUGET_FEED_URL", "The NuGet source that serves the DGF.API package.", group="Images and feeds"),
        var("NUGET_FEED_TOKEN", "The access token for that feed.", True, group="Images and feeds"),
        var("TLS_CERT_DIR", "A directory holding cert.pem and key.pem for the hosts below. The host sets its cookies "
            "secure-only, so the stack must serve HTTPS.", example="./certs"),
        var("COOKIE_DOMAIN", "The domain the session cookies are set on.", example=".localtest.me"),
        var("RA_BASE_URL", "The Registration Authority every DGF integration authenticates through.",
            group="Integrations"),
        var("RA_CALLING_SERVICE", "The calling service name presented to the Registration Authority.",
            group="Integrations"),
        var("RA_CERTIFICATE_THUMBPRINT", "The thumbprint of the certificate registered for this service.",
            group="Integrations"),
        var("RA_PRIVATE_KEY", "The private key that signs the token request.", True, group="Integrations"),
        var("SIGN_BASE_URL", "The signing service.", group="Integrations"),
        var("SIGN_SERVICE", "The service name the signing scope belongs to.", group="Integrations"),
        var("SIGN_SCOPE", "The scope requested for signing.", group="Integrations"),
        var("NOTIFY_BASE_URL", "The notification service.", group="Integrations"),
        var("NOTIFY_SERVICE", "The service name the notification scope belongs to.", group="Integrations"),
        var("NOTIFY_SCOPE", "The scope requested for notification.", group="Integrations"),
        var("NOTIFY_SENDER_EMAIL", "The sender address of the notifications the hosts send.", group="Integrations"),
    ]
    if any_basic:
        v += [var("ADMIN_USERNAME", "The user name of the first administrator, seeded at first start.",
                  example="admin", group="Sign-in"),
              var("ADMIN_PASSWORD", "The password of the first administrator.", True, group="Sign-in"),
              var("ADMIN_EMAIL", "The e-mail address of the first administrator.", group="Sign-in")]
    if supply == "mount":
        v.append(var("DGF_BASE_WORKSPACE", "The absolute path of the base workspace directory, named webasm.",
                     group="Images and feeds"))
    for dep in deployments:
        pfx = dep["pfx"]
        group = f"Deployment {dep['api']} / {dep['name']}"
        v += [var(f"{pfx}_UI_HOST", f"The host name the {dep['name']} UI is served on.", group=group),
              var(f"{pfx}_API_HOST", f"The host name the {dep['name']} API is served on.", group=group)]
        if dep["has_dgpass"]:
            v += [var(f"{pfx}_DGPASS_AUTHORITY", "The DGPass authority (issuer) URL.", group=group),
                  var(f"{pfx}_DGPASS_CLIENT_ID", "The client id registered with DGPass.", group=group),
                  var(f"{pfx}_DGPASS_CLIENT_SECRET", "The client secret registered with DGPass.", True, group=group)]
        if dep["has_azure"]:
            v += [var(f"{pfx}_AZURE_AUTHORITY", "The Azure AD authority URL, without the tenant.", group=group),
                  var(f"{pfx}_AZURE_TENANT_ID", "The Azure AD tenant id.", group=group),
                  var(f"{pfx}_AZURE_CLIENT_ID", "The application (client) id.", group=group),
                  var(f"{pfx}_AZURE_CLIENT_SECRET", "The client secret.", True, group=group)]
    seen = set()
    for item in v:
        if item["name"] in seen:
            raise ValueError(f"variable {item['name']} declared twice")
        seen.add(item["name"])
    return v
