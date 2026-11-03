FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /src
COPY . .
RUN dotnet build Inspections.Database.sqlproj -c Release -o /dacpac

FROM mcr.microsoft.com/dotnet/sdk:10.0
# sqlpackage goes to a shared tool path, so the publish runs as an unprivileged user, never as root.
RUN dotnet tool install --tool-path /opt/sqlpackage microsoft.sqlpackage \
 && groupadd --gid 4000 dbdeploy \
 && useradd --uid 4000 --gid 4000 --no-create-home dbdeploy
ENV PATH="${PATH}:/opt/sqlpackage"
WORKDIR /db
COPY --chown=4000:4000 --from=build /dacpac/Inspections.Database.dacpac .
COPY --chown=4000:4000 Inspections.Database.publish.xml .
COPY --chown=4000:4000 entrypoint.sh .
USER 4000
ENTRYPOINT ["/bin/bash", "/db/entrypoint.sh"]
