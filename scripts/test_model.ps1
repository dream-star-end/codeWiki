param(
    [string]$BaseUrl = $env:API_BASE,
    [string]$ApiKey = $env:API_KEY,
    [string]$Model = $env:MODEL_NAME
)

$ErrorActionPreference = "Stop"

if (-not $BaseUrl) { throw "API_BASE is required (or pass -BaseUrl)." }
if (-not $ApiKey) { throw "API_KEY is required (or pass -ApiKey)." }
if (-not $Model) { throw "MODEL_NAME is required (or pass -Model)." }

$headers = @{
    "Authorization" = "Bearer $ApiKey"
    "Content-Type"  = "application/json"
}

Write-Host "==> Checking models at $BaseUrl/models"
try {
    $modelsResponse = Invoke-RestMethod -Method Get -Uri "$BaseUrl/models" -Headers $headers
    $modelIds = @()
    if ($modelsResponse.data) {
        $modelIds = $modelsResponse.data | ForEach-Object { $_.id }
    }
    if ($modelIds.Count -gt 0) {
        Write-Host ("Available models: " + ($modelIds -join ", "))
        if ($modelIds -contains $Model) {
            Write-Host "Model '$Model' is listed."
        } else {
            Write-Host "Model '$Model' is NOT listed."
        }
    } else {
        Write-Host "No model list returned."
        $modelsResponse | ConvertTo-Json -Depth 6
    }
} catch {
    Write-Host "Failed to query /models:"
    Write-Host $_.Exception.Message
}

Write-Host "`n==> Checking chat/completions with model '$Model'"
$payload = @{
    model    = $Model
    messages = @(
        @{ role = "user"; content = "ping" }
    )
} | ConvertTo-Json -Depth 6

try {
    $resp = Invoke-RestMethod -Method Post -Uri "$BaseUrl/chat/completions" -Headers $headers -Body $payload
    Write-Host "Chat completion OK."
    if ($resp.choices -and $resp.choices.Count -gt 0) {
        Write-Host ("Sample: " + $resp.choices[0].message.content)
    } else {
        $resp | ConvertTo-Json -Depth 6
    }
} catch {
    Write-Host "Chat completion failed:"
    Write-Host $_.Exception.Message
    if ($_.ErrorDetails -and $_.ErrorDetails.Message) {
        Write-Host $_.ErrorDetails.Message
    }
}
