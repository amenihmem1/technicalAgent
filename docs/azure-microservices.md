# Azure Technical Microservices Deployment

This deployment keeps the same runtime split as Docker Compose:

| Azure Web App | Container image | Service |
| --- | --- | --- |
| `technique-agent-gateway-service` | `technique-agent-gateway-service` | Public Nginx gateway |
| `technique-agent-interview-service` | `technique-agent-interview-service` | Technical session lifecycle and messages |
| `technique-agent-media-service` | `technique-agent-media-service` | STT, TTS, vision, audio, proctoring |
| `technique-agent-analytics-service` | `technique-agent-analytics-service` | Technical dashboard aggregation |
| `technique-agent-reporting-service` | `technique-agent-reporting-service` | Technical and insights PDFs |
| `technical-agent-frontend` | Node.js standalone package | Next.js frontend |

## Required Azure resources

Create one Azure Container Registry, five Linux Web Apps for backend containers, and one Linux Node.js Web App for the frontend:

- `technique-agent-gateway-service`
- `technique-agent-interview-service`
- `technique-agent-media-service`
- `technique-agent-analytics-service`
- `technique-agent-reporting-service`
- `technical-agent-frontend`

You can create the backend container resources with:

```powershell
./scripts/azure/create-microservices.ps1 `
  -ResourceGroup "tech-agent-rg" `
  -Location "francecentral" `
  -PlanName "tech-agent-linux-plan" `
  -AcrName "techagentacr"
```

## GitHub secrets

Add these repository secrets:

```text
AZURE_CONTAINER_REGISTRY_LOGIN_SERVER
AZURE_CONTAINER_REGISTRY_USERNAME
AZURE_CONTAINER_REGISTRY_PASSWORD
```

The microservice workflow pushes `:latest` images. App Service container continuous deployment pulls the updated images from ACR.

## Gateway app settings

Set these app settings on `technique-agent-gateway-service`:

```text
WEBSITES_PORT=8000
INTERVIEW_SERVICE_URL=https://technique-agent-interview-service.azurewebsites.net
MEDIA_SERVICE_URL=https://technique-agent-media-service.azurewebsites.net
ANALYTICS_SERVICE_URL=https://technique-agent-analytics-service.azurewebsites.net
REPORTING_SERVICE_URL=https://technique-agent-reporting-service.azurewebsites.net
```

## Backend service app settings

Set shared runtime settings on backend services:

```text
WEBSITES_PORT=8000
DATABASE_URL=<postgres connection string>
PUBLIC_APP_URL=https://technical-agent-frontend.azurewebsites.net
CORS_ALLOW_ORIGINS=https://technical-agent-frontend.azurewebsites.net
SESSION_STORE_REQUIRE_POSTGRES=true
SESSION_STORE_ALLOW_JSON_FALLBACK=false
```

Also copy API keys needed by the services that use them, for example:

```text
AZURE_OPENAI_API_KEY
AZURE_OPENAI_ENDPOINT
DEEPGRAM_API_KEY
CARTESIA_API_KEY
```

## Frontend app settings

Set the frontend backend base URL to the public gateway:

```text
TECH_API_BASE_URL=https://technique-agent-gateway-service.azurewebsites.net
NEXT_PUBLIC_APP_URL=https://technical-agent-frontend.azurewebsites.net
NEXT_PUBLIC_REPORT_SHARE_BASE_URL=https://technical-agent-frontend.azurewebsites.net
```
