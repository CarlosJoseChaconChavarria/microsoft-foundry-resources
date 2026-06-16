@minLength(1)
@maxLength(64)
param environmentName string

@minLength(1)
param location string = resourceGroup().location

var resourceToken = toLower(uniqueString(subscription().id, environmentName, location))
var tags = { 'azd-env-name': environmentName }

// Resource names
var storageName      = 'st${resourceToken}'
var logAnalyticsName = 'logs-${resourceToken}'
var appInsightsName  = 'appi-${resourceToken}'
var aiServicesName   = 'ai-${resourceToken}'
var hubName          = 'hub-${resourceToken}'
var projectName      = 'workshop-project'
var modelName        = 'gpt-4o'

// ── Storage (required by Hub) ─────────────────────────────────────────────
resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageName
  location: location
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  tags: tags
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
  }
}

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

// ── Azure AI Services (hosts gpt-4o) ─────────────────────────────────────
resource aiServices 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: aiServicesName
  location: location
  kind: 'AIServices'
  sku: { name: 'S0' }
  tags: tags
  identity: { type: 'SystemAssigned' }
  properties: {
    customSubDomainName: aiServicesName
    publicNetworkAccess: 'Enabled'
  }
}

// ── gpt-4o deployment ─────────────────────────────────────────────────────
resource gpt4o 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
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

// ── Azure AI Foundry Hub ──────────────────────────────────────────────────
resource hub 'Microsoft.MachineLearningServices/workspaces@2024-10-01' = {
  name: hubName
  location: location
  kind: 'Hub'
  tags: tags
  identity: { type: 'SystemAssigned' }
  properties: {
    friendlyName: 'Foundry Workshop Hub'
    storageAccount: storage.id
    publicNetworkAccess: 'Enabled'
    workspaceHubConfig: {
      defaultWorkspaceResourceGroup: resourceGroup().id
    }
  }
}

// Grant Hub's managed identity access to AI Services
resource hubAiRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(aiServices.id, hub.id, 'CognitiveServicesUser')
  scope: aiServices
  properties: {
    principalId: hub.identity.principalId
    principalType: 'ServicePrincipal'
    // Cognitive Services User
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908')
  }
}

// Connect Hub → AI Services
resource aiConnection 'Microsoft.MachineLearningServices/workspaces/connections@2024-10-01' = {
  parent: hub
  name: 'ai-services'
  properties: {
    category: 'AIServices'
    target: aiServices.properties.endpoint
    authType: 'AAD'
    isSharedToAll: true
    metadata: {
      ApiType: 'Azure'
      ResourceId: aiServices.id
    }
  }
  dependsOn: [hubAiRole]
}

// ── Azure AI Foundry Project ──────────────────────────────────────────────
resource project 'Microsoft.MachineLearningServices/workspaces@2024-10-01' = {
  name: projectName
  location: location
  kind: 'Project'
  tags: tags
  identity: { type: 'SystemAssigned' }
  properties: {
    friendlyName: 'Workshop Project'
    hubResourceId: hub.id
    publicNetworkAccess: 'Enabled'
  }
  dependsOn: [aiConnection]
}

// ── Outputs (picked up by azd and passed to post-provision hook) ──────────
output AZURE_RESOURCE_GROUP      string = resourceGroup().name
output FOUNDRY_AI_SERVICES_NAME  string = aiServices.name
output FOUNDRY_PROJECT_NAME      string = project.name
output FOUNDRY_MODEL             string = gpt4o.name
output APPLICATIONINSIGHTS_CONNECTION_STRING string = appInsights.properties.ConnectionString
