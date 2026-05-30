param(
  [string]$ResourceGroup = "tech-agent-rg",
  [string]$Location = "francecentral",
  [string]$PlanName = "tech-agent-linux-plan",
  [string]$AcrName = "techagentacr",
  [string]$Sku = "B1",
  [string]$FrontendUrl = "https://technical-agent-frontend.azurewebsites.net",
  [string]$DatabaseUrl = "",
  [string]$AzureOpenAiApiKey = "",
  [string]$AzureOpenAiEndpoint = "",
  [string]$DeepgramApiKey = "",
  [string]$CartesiaApiKey = ""
)

$ErrorActionPreference = "Stop"

function Invoke-Az {
  $Arguments = $args
  & az @Arguments
  if ($LASTEXITCODE -ne 0) {
    throw "Azure CLI command failed: az $($Arguments -join ' ')"
  }
}

function Get-AzValueOrNull {
  $Arguments = $args
  $oldErrorActionPreference = $ErrorActionPreference
  $ErrorActionPreference = "Continue"
  try {
    $output = & az @Arguments 2>$null
    if ($LASTEXITCODE -eq 0 -and $output) {
      return ($output | Select-Object -First 1)
    }
    return $null
  } finally {
    $ErrorActionPreference = $oldErrorActionPreference
  }
}

function Set-AppSettings {
  param([string]$Name, [hashtable]$Settings)

  $pairs = @()
  foreach ($key in $Settings.Keys) {
    $value = [string]$Settings[$key]
    if ($value.Length -gt 0) {
      $pairs += "$key=$value"
    }
  }

  if ($pairs.Count -gt 0) {
    Invoke-Az webapp config appsettings set --resource-group $ResourceGroup --name $Name --settings $pairs | Out-Null
  }
}

$existingGroupLocation = Get-AzValueOrNull group show --name $ResourceGroup --query location -o tsv
if ($existingGroupLocation) {
  $Location = $existingGroupLocation
} else {
  Invoke-Az group create --name $ResourceGroup --location $Location | Out-Null
}

if (-not (Get-AzValueOrNull appservice plan show --name $PlanName --resource-group $ResourceGroup --query name -o tsv)) {
  Invoke-Az appservice plan create --name $PlanName --resource-group $ResourceGroup --location $Location --is-linux --sku $Sku | Out-Null
}

if (Get-AzValueOrNull acr show --name $AcrName --resource-group $ResourceGroup --query name -o tsv) {
  Invoke-Az acr update --resource-group $ResourceGroup --name $AcrName --admin-enabled true | Out-Null
} else {
  Invoke-Az acr create --resource-group $ResourceGroup --name $AcrName --location $Location --sku Basic --admin-enabled true | Out-Null
}

$acrLoginServer = Invoke-Az acr show --name $AcrName --resource-group $ResourceGroup --query loginServer -o tsv
$acrUsername = Invoke-Az acr credential show --name $AcrName --query username -o tsv
$acrPassword = Invoke-Az acr credential show --name $AcrName --query "passwords[0].value" -o tsv

$services = @(
  @{ Name = "technique-agent-interview-service"; Image = "technique-agent-interview-service" },
  @{ Name = "technique-agent-media-service"; Image = "technique-agent-media-service" },
  @{ Name = "technique-agent-analytics-service"; Image = "technique-agent-analytics-service" },
  @{ Name = "technique-agent-reporting-service"; Image = "technique-agent-reporting-service" },
  @{ Name = "technique-agent-gateway-service"; Image = "technique-agent-gateway-service" }
)

foreach ($service in $services) {
  $name = $service.Name
  $image = "$acrLoginServer/$($service.Image):latest"

  if (-not (Get-AzValueOrNull webapp show --resource-group $ResourceGroup --name $name --query name -o tsv)) {
    Invoke-Az webapp create --resource-group $ResourceGroup --plan $PlanName --name $name --deployment-container-image-name $image | Out-Null
  }

  Invoke-Az webapp config container set `
    --resource-group $ResourceGroup `
    --name $name `
    --docker-custom-image-name $image `
    --docker-registry-server-url "https://$acrLoginServer" `
    --docker-registry-server-user $acrUsername `
    --docker-registry-server-password $acrPassword | Out-Null

  Set-AppSettings -Name $name -Settings @{
    WEBSITES_PORT = "8000"
    WEBSITE_WEBDEPLOY_USE_SCM = "true"
    DOCKER_ENABLE_CI = "true"
    WEBSITES_CONTAINER_START_TIME_LIMIT = "1800"
    SCM_COMMAND_IDLE_TIMEOUT = "1800"
    DOCKER_REGISTRY_SERVER_URL = "https://$acrLoginServer"
    DOCKER_REGISTRY_SERVER_USERNAME = $acrUsername
    DOCKER_REGISTRY_SERVER_PASSWORD = $acrPassword
  }

  Invoke-Az webapp deployment container config --resource-group $ResourceGroup --name $name --enable-cd true | Out-Null
}

Set-AppSettings -Name "technique-agent-gateway-service" -Settings @{
  INTERVIEW_SERVICE_URL = "https://technique-agent-interview-service.azurewebsites.net"
  MEDIA_SERVICE_URL = "https://technique-agent-media-service.azurewebsites.net"
  ANALYTICS_SERVICE_URL = "https://technique-agent-analytics-service.azurewebsites.net"
  REPORTING_SERVICE_URL = "https://technique-agent-reporting-service.azurewebsites.net"
}

$backendSettings = @{
  DATABASE_URL = $DatabaseUrl
  SESSION_STORE_REQUIRE_POSTGRES = "true"
  SESSION_STORE_ALLOW_JSON_FALLBACK = "false"
  PUBLIC_APP_URL = $FrontendUrl
  CORS_ALLOW_ORIGINS = $FrontendUrl
  AZURE_OPENAI_API_KEY = $AzureOpenAiApiKey
  AZURE_OPENAI_ENDPOINT = $AzureOpenAiEndpoint
  DEEPGRAM_API_KEY = $DeepgramApiKey
  CARTESIA_API_KEY = $CartesiaApiKey
  EMOTION_BACKEND_PROVIDER = "custom"
  CUSTOM_EMOTION_MODEL_DIR = "/app/data/models/emotion/efficientnet_b3_20260425_053142"
}

foreach ($name in @("technique-agent-interview-service", "technique-agent-media-service", "technique-agent-analytics-service", "technique-agent-reporting-service")) {
  Set-AppSettings -Name $name -Settings $backendSettings
}

Write-Host "Done. Add these GitHub Actions secrets:"
Write-Host "AZURE_CONTAINER_REGISTRY_LOGIN_SERVER=$acrLoginServer"
Write-Host "AZURE_CONTAINER_REGISTRY_USERNAME=$acrUsername"
Write-Host "AZURE_CONTAINER_REGISTRY_PASSWORD=<hidden>"
Write-Host ""
Write-Host "Set technical-agent-frontend app settings:"
Write-Host "TECH_API_BASE_URL=https://technique-agent-gateway-service.azurewebsites.net"
Write-Host "NEXT_PUBLIC_APP_URL=$FrontendUrl"
Write-Host "NEXT_PUBLIC_REPORT_SHARE_BASE_URL=$FrontendUrl"
