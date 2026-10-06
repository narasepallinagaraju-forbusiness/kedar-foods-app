param(
    [ValidateSet("prod", "dev")]
    [string]$Env = "prod",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$region = "ap-south-1"
$stackName = "kedar-foods-app-$Env-frontend"
$projectRoot = Split-Path -Parent $PSScriptRoot
$outputDirectory = Join-Path $projectRoot "out"

function Invoke-AwsCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,
        [switch]$ShowOutput
    )

    $commandText = "aws " + ($Arguments -join " ")
    Write-Host "> $commandText"
    $commandOutput = & aws @Arguments 2>&1
    $commandExitCode = $LASTEXITCODE

    if ($ShowOutput) {
        foreach ($line in $commandOutput) {
            Write-Host ([string]$line)
        }
    }

    if ($commandExitCode -ne 0) {
        $details = ($commandOutput | ForEach-Object { [string]$_ }) -join `
            [Environment]::NewLine
        throw "Command failed (exit $commandExitCode): $commandText`n$details"
    }

    return ($commandOutput | ForEach-Object { [string]$_ }) -join `
        [Environment]::NewLine
}

function Test-UploadedContentType {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Bucket,
        [Parameter(Mandatory = $true)]
        [string]$Key,
        [Parameter(Mandatory = $true)]
        [string[]]$ExpectedTypes,
        [Parameter(Mandatory = $true)]
        [AllowEmptyCollection()]
        [System.Collections.Generic.List[string]]$Results
    )

    $actualType = Invoke-AwsCommand -Arguments @(
        "s3api",
        "head-object",
        "--bucket",
        $Bucket,
        "--key",
        $Key,
        "--query",
        "ContentType",
        "--output",
        "text",
        "--region",
        $region
    )
    $actualType = $actualType.Trim()
    if ($ExpectedTypes -contains $actualType) {
        $Results.Add("PASS ${Key}: $actualType")
    }
    else {
        Write-Warning "Content type mismatch for '$Key': actual '$actualType'; expected $($ExpectedTypes -join ' or ')."
        $Results.Add("WARN ${Key}: actual '$actualType'; expected $($ExpectedTypes -join ' or ')")
    }
}

try {
    $requiredFiles = @(
        "index.html",
        "404.html",
        "products/_shell.html"
    )
    if (-not (Test-Path -LiteralPath $outputDirectory -PathType Container)) {
        throw "Static export folder 'out/' is missing. Run 'npm run build' first."
    }
    foreach ($relativeFile in $requiredFiles) {
        $requiredPath = Join-Path $outputDirectory $relativeFile
        if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
            throw "Required static export file 'out/$relativeFile' is missing. Run 'npm run build' first."
        }
    }

    $identityJson = Invoke-AwsCommand -Arguments @(
        "sts",
        "get-caller-identity",
        "--region",
        $region,
        "--output",
        "json"
    )
    $accountId = ($identityJson | ConvertFrom-Json).Account
    if ([string]::IsNullOrWhiteSpace($accountId)) {
        throw "AWS STS did not return an account ID."
    }

    $stackJson = Invoke-AwsCommand -Arguments @(
        "cloudformation",
        "describe-stacks",
        "--stack-name",
        $stackName,
        "--region",
        $region,
        "--output",
        "json"
    )
    $stack = ($stackJson | ConvertFrom-Json).Stacks | Select-Object -First 1
    if ($null -eq $stack) {
        throw "CloudFormation returned no stack named '$stackName'."
    }

    $frontendBucket = (
        $stack.Outputs | Where-Object { $_.OutputKey -eq "FrontendBucketName" } |
            Select-Object -First 1
    ).OutputValue
    $distributionId = (
        $stack.Outputs | Where-Object { $_.OutputKey -eq "DistributionId" } |
            Select-Object -First 1
    ).OutputValue
    $siteDomain = (
        $stack.Outputs | Where-Object { $_.OutputKey -eq "SiteDomain" } |
            Select-Object -First 1
    ).OutputValue

    if (
        [string]::IsNullOrWhiteSpace($frontendBucket) -or
        [string]::IsNullOrWhiteSpace($distributionId) -or
        [string]::IsNullOrWhiteSpace($siteDomain)
    ) {
        throw "Stack '$stackName' must provide FrontendBucketName, DistributionId, and SiteDomain outputs."
    }

    Write-Host "AWS account: $accountId"
    Write-Host "Region: $region"
    Write-Host "Frontend bucket: $frontendBucket"
    Write-Host "CloudFront distribution: $distributionId"

    if (-not $DryRun) {
        $confirmation = Read-Host 'Type "yes" to upload the static frontend'
        if ($confirmation -cne "yes") {
            throw "Upload cancelled; confirmation must be exactly 'yes'."
        }
    }

    $nextSyncArguments = @(
        "s3",
        "sync",
        (Join-Path $outputDirectory "_next"),
        "s3://$frontendBucket/_next",
        "--cache-control",
        "public, max-age=31536000, immutable",
        "--region",
        $region
    )
    $restSyncArguments = @(
        "s3",
        "sync",
        $outputDirectory,
        "s3://$frontendBucket",
        "--exclude",
        "_next/*",
        "--cache-control",
        "public, max-age=60",
        "--delete",
        "--region",
        $region
    )
    if ($DryRun) {
        $nextSyncArguments += "--dryrun"
        $restSyncArguments += "--dryrun"
        Write-Host "Dry run: sync commands will use --dryrun; no invalidation will be created."
        Write-Host "Top-level contents of out/:"
        Get-ChildItem -LiteralPath $outputDirectory -Force |
            Select-Object Mode, Length, Name |
            Format-Table -AutoSize |
            Out-String |
            Write-Host
    }

    [void](Invoke-AwsCommand -Arguments $nextSyncArguments -ShowOutput)
    [void](Invoke-AwsCommand -Arguments $restSyncArguments -ShowOutput)

    if (-not $DryRun) {
        $contentTypeResults = [System.Collections.Generic.List[string]]::new()
        Test-UploadedContentType `
            -Bucket $frontendBucket `
            -Key "index.html" `
            -ExpectedTypes @("text/html") `
            -Results $contentTypeResults

        $staticDirectory = Join-Path $outputDirectory "_next\static"
        foreach ($extension in @(".js", ".css")) {
            $asset = Get-ChildItem -LiteralPath $staticDirectory -Filter "*$extension" `
                -File -Recurse -ErrorAction SilentlyContinue |
                Sort-Object FullName |
                Select-Object -First 1
            if ($null -eq $asset) {
                $message = "No $extension file found under out/_next/static/."
                Write-Warning $message
                $contentTypeResults.Add("SKIP $extension check: $message")
                continue
            }

            $assetKey = $asset.FullName.Substring($outputDirectory.Length).
                TrimStart([char[]]@([char]92, [char]47)).
                Replace([char]92, [char]47)
            if ($extension -eq ".js") {
                $expectedTypes = @("text/javascript", "application/javascript")
            }
            else {
                $expectedTypes = @("text/css")
            }
            Test-UploadedContentType `
                -Bucket $frontendBucket `
                -Key $assetKey `
                -ExpectedTypes $expectedTypes `
                -Results $contentTypeResults
        }

        Write-Host "Content-type verification summary:"
        foreach ($result in $contentTypeResults) {
            Write-Host "  $result"
        }

        $invalidationJson = Invoke-AwsCommand -Arguments @(
            "cloudfront",
            "create-invalidation",
            "--distribution-id",
            $distributionId,
            "--paths",
            "/*",
            "--region",
            $region,
            "--output",
            "json"
        )
        $invalidationId = ($invalidationJson | ConvertFrom-Json).Invalidation.Id
        if ([string]::IsNullOrWhiteSpace($invalidationId)) {
            throw "CloudFront did not return an invalidation ID."
        }
        Write-Host "CloudFront invalidation ID: $invalidationId"
    }

    Write-Host "Site URL: https://$siteDomain"
    Write-Host "Remember to run the six routing tests against the deployed site."
}
catch {
    Write-Error "Frontend deployment failed: $($_.Exception.Message)"
    exit 1
}
