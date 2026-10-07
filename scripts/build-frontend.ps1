param(
    [ValidateSet("prod", "dev")]
    [string]$Env = "prod"
)

$ErrorActionPreference = "Stop"
$region = "ap-south-1"
$stackName = "kedar-foods-app-$Env-backend"
$projectRoot = Split-Path -Parent $PSScriptRoot

try {
    Write-Host "> aws cloudformation describe-stacks --stack-name $stackName --region $region --output json"
    $stackOutput = & aws cloudformation describe-stacks `
        --stack-name $stackName `
        --region $region `
        --output json 2>&1
    $awsExitCode = $LASTEXITCODE
    if ($awsExitCode -ne 0) {
        $details = ($stackOutput | ForEach-Object { [string]$_ }) -join [Environment]::NewLine
        throw "Unable to read ApiUrl from stack '$stackName' (AWS CLI exit $awsExitCode).`n$details"
    }

    $stackResponse = ($stackOutput | ForEach-Object { [string]$_ }) -join [Environment]::NewLine
    $stack = ($stackResponse | ConvertFrom-Json).Stacks | Select-Object -First 1
    if ($null -eq $stack) {
        throw "CloudFormation returned no stack named '$stackName'."
    }

    $apiUrl = [string](
        $stack.Outputs |
            Where-Object { $_.OutputKey -eq "ApiUrl" } |
            Select-Object -First 1
    ).OutputValue
    if ([string]::IsNullOrWhiteSpace($apiUrl)) {
        throw "Stack '$stackName' has no non-empty ApiUrl output."
    }

    $apiUri = $null
    if (-not [Uri]::TryCreate($apiUrl, [UriKind]::Absolute, [ref]$apiUri) -or $apiUri.Scheme -notin @("http", "https")) {
        throw "Stack '$stackName' returned an invalid ApiUrl: '$apiUrl'."
    }

    $env:NEXT_PUBLIC_API_BASE_URL = $apiUrl.TrimEnd("/")
    Write-Host "Building frontend for '$Env' with API URL $env:NEXT_PUBLIC_API_BASE_URL"
    Push-Location $projectRoot
    try {
        & npm run build
        if ($LASTEXITCODE -ne 0) {
            throw "npm run build failed with exit code $LASTEXITCODE."
        }
    }
    finally {
        Pop-Location
    }
}
catch {
    Write-Error "Frontend build failed: $($_.Exception.Message)"
    exit 1
}
