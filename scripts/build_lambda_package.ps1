# PANDOK Python 코드와 Linux용 의존성을 AWS Lambda 배포 ZIP으로 만든다.
# Windows에서 만든 가상환경을 그대로 올려 발생하는 운영체제 호환 오류를 막기 위해 필요하다.

param(
    [ValidateSet("x86_64", "arm64")]
    [string]$Architecture = "x86_64"
)

$ErrorActionPreference = "Stop"

$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$buildRoot = Join-Path $repositoryRoot "build"
$packageDirectory = Join-Path $buildRoot "lambda-package"
$zipPath = Join-Path $buildRoot "pandok-ingestion-lambda.zip"
$contractDirectory = Join-Path $packageDirectory "contracts"
$contractPath = Join-Path $repositoryRoot "contracts\telemetry-event-v2.schema.json"
$contractSource = Join-Path $repositoryRoot "src\pandok_contracts"
$ingestionSource = Join-Path $repositoryRoot "src\pandok_ingestion"

# 이전 빌드 파일이 새 패키지에 섞이지 않도록 저장소 내부 build 경로만 초기화한다.
if (Test-Path -LiteralPath $packageDirectory) {
    Remove-Item -LiteralPath $packageDirectory -Recurse -Force
}

if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}

New-Item -ItemType Directory -Path $packageDirectory -Force | Out-Null

$pythonPlatform = if ($Architecture -eq "arm64") {
    "aarch64-manylinux_2_28"
} else {
    "x86_64-manylinux_2_28"
}

# Lambda에서 실제로 사용하는 Schema 검증 의존성만 Linux 패키지로 설치한다.
# Silver 전용 pyarrow와 런타임 기본 boto3를 제외해 직접 업로드 ZIP 한도를 지킨다.
uv pip install `
    --target $packageDirectory `
    --python-version 3.12 `
    --python-platform $pythonPlatform `
    "jsonschema[format]>=4.23,<5"

if ($LASTEXITCODE -ne 0) {
    throw "Lambda package dependency installation failed."
}

# ingestion Lambda가 import하는 두 Python package만 배포 파일에 복사한다.
Copy-Item -LiteralPath $contractSource -Destination $packageDirectory -Recurse
Copy-Item -LiteralPath $ingestionSource -Destination $packageDirectory -Recurse

# Validator가 Lambda 루트에서도 같은 실행 계약을 읽도록 v2 Schema를 함께 넣는다.
New-Item -ItemType Directory -Path $contractDirectory -Force | Out-Null
Copy-Item -LiteralPath $contractPath -Destination $contractDirectory

# .NET 압축 API는 파일 접근 오류를 terminating exception으로 전달해 불완전 ZIP을 성공으로 오인하지 않는다.
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory(
    $packageDirectory,
    $zipPath,
    [System.IO.Compression.CompressionLevel]::Optimal,
    $false
)

if (-not (Test-Path -LiteralPath $zipPath)) {
    throw "Lambda package ZIP was not created."
}

Write-Output "Lambda package created: $zipPath"
