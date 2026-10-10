$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$composeFile = Join-Path $projectRoot "docker-compose.yml"
$composeArgs = @("compose", "-f", $composeFile)
$servicesStarted = $false

try {
    $servicesStarted = $true
    docker @composeArgs up --build -d
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Compose failed to build or start the services."
    }

    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        try {
            $null = Invoke-RestMethod -Uri "http://localhost:8080/healthz" -TimeoutSec 2
            $null = Invoke-RestMethod -Uri "http://localhost:8081/healthz" -TimeoutSec 2
            $ready = $true
            break
        }
        catch {
            Start-Sleep -Seconds 1
        }
    }
    if (-not $ready) {
        throw "Services did not become healthy within 30 seconds."
    }

    $order = Invoke-RestMethod -Method Post -Uri "http://localhost:8080/orders" `
        -ContentType "application/json" -Body '{"sku":"sku-100","qty":2}'
    $stock = Invoke-RestMethod -Uri "http://localhost:8081/stock/sku-100"
    if ($order.status -ne "confirmed" -or $stock.available -ne 48) {
        throw "Unexpected order or inventory response."
    }

    Write-Host "Local smoke test passed. Order $($order.order_id) reserved 2 units; 48 remain."
}
catch {
    if ($servicesStarted) {
        docker @composeArgs logs
    }
    throw
}
finally {
    if ($servicesStarted) {
        docker @composeArgs down --remove-orphans
    }
}
