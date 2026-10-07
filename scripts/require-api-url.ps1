$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($env:NEXT_PUBLIC_API_BASE_URL)) {
    throw "NEXT_PUBLIC_API_BASE_URL is required for a production build. Run 'npm run build:frontend' or set an explicit API URL."
}

$apiUri = $null
if (-not [Uri]::TryCreate($env:NEXT_PUBLIC_API_BASE_URL, [UriKind]::Absolute, [ref]$apiUri)) {
    throw "NEXT_PUBLIC_API_BASE_URL must be a valid absolute HTTP or HTTPS URL."
}
if ($apiUri.Scheme -notin @("http", "https")) {
    throw "NEXT_PUBLIC_API_BASE_URL must use HTTP or HTTPS."
}
