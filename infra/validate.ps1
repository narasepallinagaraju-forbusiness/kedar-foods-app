$ErrorActionPreference = "Continue"

$logPath = Join-Path $PSScriptRoot "validation-results.txt"
$overallExitCode = 0

Set-Content -Path $logPath -Value "Frontend infrastructure validation" -Encoding UTF8
Add-Content -Path $logPath -Value "Started: $(Get-Date -Format o)"

function Invoke-LoggedCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$CommandText,
        [Parameter(Mandatory = $true)]
        [scriptblock]$Command
    )

    Add-Content -Path $logPath -Value "`r`n> $CommandText"
    Write-Host "`n> $CommandText"

    try {
        $commandOutput = & $Command 2>&1
        $commandExitCode = $LASTEXITCODE
        if ($null -eq $commandExitCode) {
            $commandExitCode = 0
        }
        foreach ($line in $commandOutput) {
            $text = [string]$line
            Add-Content -Path $logPath -Value $text
            Write-Host $text
        }
    }
    catch {
        $commandExitCode = 1
        $errorText = $_ | Out-String
        Add-Content -Path $logPath -Value $errorText
        Write-Host $errorText
    }

    Add-Content -Path $logPath -Value "Exit code: $commandExitCode"
    Write-Host "Exit code: $commandExitCode"

    if ($commandExitCode -ne 0) {
        $script:overallExitCode = 1
    }
}

Invoke-LoggedCommand "infra\.venv\Scripts\ruff.exe check infra" {
    & (Join-Path $PSScriptRoot ".venv\Scripts\ruff.exe") check $PSScriptRoot
}
Invoke-LoggedCommand "infra\.venv\Scripts\mypy.exe infra" {
    & (Join-Path $PSScriptRoot ".venv\Scripts\mypy.exe") $PSScriptRoot
}
Invoke-LoggedCommand "infra\.venv\Scripts\pytest.exe infra\tests" {
    & (Join-Path $PSScriptRoot ".venv\Scripts\pytest.exe") (Join-Path $PSScriptRoot "tests")
}

if (Test-Path (Join-Path $PSScriptRoot "..\out")) {
    Invoke-LoggedCommand "node scripts/test-routing-function.mjs" {
        Push-Location (Join-Path $PSScriptRoot "..")
        try {
            & node scripts/test-routing-function.mjs
        }
        finally {
            Pop-Location
        }
    }
}
else {
    Add-Content -Path $logPath -Value "`r`n> node scripts/test-routing-function.mjs`r`nSkipped: out\ is missing; no build was run."
    Write-Host "Skipped routing test: out\ is missing; no build was run."
    $overallExitCode = 1
}

Push-Location $PSScriptRoot
$env:PATH = "$PSScriptRoot\.venv\Scripts;$env:PATH"
try {
    Invoke-LoggedCommand "cdk synth -c env=prod" {
        & cdk synth -c env=prod
    }
    Invoke-LoggedCommand "cdk synth -c env=prod -c domainName=example.com -c certificateArn=arn:aws:acm:us-east-1:123456789012:certificate/00000000-0000-0000-0000-000000000000" {
        & cdk synth -c env=prod -c domainName=example.com -c certificateArn=arn:aws:acm:us-east-1:123456789012:certificate/00000000-0000-0000-0000-000000000000
    }
    Invoke-LoggedCommand "cdk synth -c env=dev" {
        & cdk synth -c env=dev
    }
}
finally {
    Pop-Location
}

Add-Content -Path $logPath -Value "`r`nFinished: $(Get-Date -Format o)"
Add-Content -Path $logPath -Value "Overall exit code: $overallExitCode"
Write-Host "`nValidation log: $logPath"
exit $overallExitCode
