FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /src
COPY . .
RUN dotnet build Inspections.Database.sqlproj -c Release -o /dacpac

FROM mcr.microsoft.com/dotnet/sdk:10.0
RUN dotnet tool install -g microsoft.sqlpackage
ENV PATH="${PATH}:/root/.dotnet/tools"
WORKDIR /db
COPY --from=build /dacpac/Inspections.Database.dacpac .
COPY Inspections.Database.publish.xml .
COPY entrypoint.sh .
ENTRYPOINT ["/bin/bash", "/db/entrypoint.sh"]
