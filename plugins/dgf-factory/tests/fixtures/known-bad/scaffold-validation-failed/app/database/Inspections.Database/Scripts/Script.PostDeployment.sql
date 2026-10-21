/*
  Post-deployment script. It uses the SQLCMD include idiom, and every included script is idempotent:
  a publish runs against an empty database and against an existing one.
*/
:r ../ContinuousDeployment/1.PostDeployment.Applications.sql
:r ../ContinuousDeployment/2.PostDeployment.Roles.sql
