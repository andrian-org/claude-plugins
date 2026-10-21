using DGF.API;
using DGF.Infrastructure.Persistence.Seed;

var builder = WebApplication.CreateBuilder(args);

await builder.BuildEServicesApi(
    postAppConfigure: app =>
    {
        // Seeds the administrator accounts named in AdminSeedOptions, once, at first start.
        var seeder = app.Services.CreateScope().ServiceProvider.GetService<ApplicationDbContextSeed>();
        seeder?.SeedAsync().GetAwaiter().GetResult();
    });
