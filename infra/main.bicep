@minLength(1)
@maxLength(64)
param environmentName string

@minLength(1)
param location string = resourceGroup().location

var resourceToken = toLower(uniqueString(subscription().id, environmentName, location))
var tags = { 'azd-env-name': environmentName }

// Resource names
var logAnalyticsName = 'logs-${resourceToken}'
var appInsightsName  = 'appi-${resourceToken}'
var aiServicesName   = 'ai-${resourceToken}'
var projectName      = 'workshop-project'
var modelName        = 'gpt-4o'

// ── Log Analytics ─────────────────────────────────────────────────────────
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: logAnalyticsName
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

// ── Application Insights ──────────────────────────────────────────────────
resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'web'
  tags: tags
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
  }
}

// ── Azure AI Foundry resource (AI Services account) ───────────────────────
// allowProjectManagement enables the /api/projects/<name> endpoint on
// services.ai.azure.com, which the agent framework uses as project_endpoint.
resource aiServices 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: aiServicesName
  location: location
  kind: 'AIServices'
  sku: { name: 'S0' }
  tags: tags
  identity: { type: 'SystemAssigned' }
  properties: {
    customSubDomainName: aiServicesName
    publicNetworkAccess: 'Enabled'
    allowProjectManagement: true
  }
}

// ── gpt-4o deployment ─────────────────────────────────────────────────────
resource gpt4o 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: aiServices
  name: modelName
  sku: {
    name: 'Standard'
    capacity: 10
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-4o'
      version: '2024-11-20'
    }
  }
}

// ── Foundry project ───────────────────────────────────────────────────────
// A CognitiveServices/accounts/projects resource is the correct type for
// the new Foundry model; it is addressable as
// https://<aiServicesName>.services.ai.azure.com/api/projects/<projectName>
resource aiProject 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  name: projectName
  parent: aiServices
  location: location
  tags: tags
  identity: { type: 'SystemAssigned' }
  properties: {}
}

// ── Outputs (picked up by azd and passed to post-provision hook) ──────────
output AZURE_RESOURCE_GROUP      string = resourceGroup().name
output FOUNDRY_AI_SERVICES_NAME  string = aiServices.name
output FOUNDRY_PROJECT_NAME      string = aiProject.name
output FOUNDRY_MODEL             string = gpt4o.name
output APPLICATIONINSIGHTS_CONNECTION_STRING string = appInsights.properties.ConnectionString
