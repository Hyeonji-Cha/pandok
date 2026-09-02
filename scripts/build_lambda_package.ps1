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

# Lambda Python 3.12와 호환되는 Linux 패키지를 애플리케이션 코드와 함께 설치한다.
uv pip install `
    --target $packageDirectory `
    --python-version 3.12 `
    --python-platform $pythonPlatform `
    $repositoryRoot

if ($LASTEXITCODE -ne 0) {
    throw "Lambda package dependency installation failed."
}

Compress-Archive `
    -Path (Join-Path $packageDirectory "*") `
    -DestinationPath $zipPath `
    -CompressionLevel Optimal

Write-Output "Lambda package created: $zipPath"
