# syntax=docker/dockerfile:1
# The build context is the application's root, so the stages copy this host's folder by its path.
FROM mcr.microsoft.com/dotnet/aspnet:10.0 AS base
WORKDIR /app
RUN apt-get update \
 && apt-get install -y --no-install-recommends libfontconfig1 libgdiplus libc6-dev libuuid1 fontconfig fonts-liberation \
 && rm -rf /var/lib/apt/lists/* \
 && fc-cache -f \
 && groupadd --gid 4000 netuser \
 && useradd --uid 4000 --gid 4000 --no-create-home netuser
ENV ASPNETCORE_URLS="http://+:{{port}}" ASPNETCORE_HTTP_PORTS={{port}}
USER 4000
EXPOSE {{port}}

FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
ARG NUGET_FEED_URL
WORKDIR /work
COPY {{api.dir}}/ {{api.dir}}/
# The feed's token arrives as a build secret, so it is never written into a layer of the final image.
RUN --mount=type=secret,id=nuget_token \
    dotnet nuget add source "${NUGET_FEED_URL}" --name dgf --username token \
      --password "$(cat /run/secrets/nuget_token)" --store-password-in-clear-text \
 && dotnet restore "{{api.dir}}/{{api.project}}"
RUN dotnet publish "{{api.dir}}/{{api.project}}" --no-restore -c Release -o /app/publish

FROM base AS final
COPY --chown=4000:4000 --from=build /app/publish .
ENTRYPOINT ["dotnet", "{{api.name}}.dll"]
