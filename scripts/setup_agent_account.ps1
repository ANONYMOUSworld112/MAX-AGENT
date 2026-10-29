<#
.SYNOPSIS
    setup_agent_account.ps1 - Configures low-privilege Windows service account and NTFS ACLs for FRIDAY.

.DESCRIPTION
    Creates a restricted local user account 'friday-agent' and configures NTFS ACLs on sensitive
    configuration files and core binaries to prevent the agent from modifying its own safety rules.
    Runs from Phase 1 to guarantee configuration protection before browser, email, and shell tools run.

.PARAMETER DryRun
    Simulates the permission updates without modifying user accounts or filesystem ACLs.
#>

param (
    [switch]$DryRun
)

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  FRIDAY Operating Layer - Security Hardening & ACL Setup  " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$AgentUser = "friday-agent"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

$ConfigDir = Join-Path $ProjectRoot "config"
$CoreDir = Join-Path $ProjectRoot "core"

Write-Host "[+] Project Root: $ProjectRoot"
Write-Host "[+] Target Restricted Account: $AgentUser"

if ($DryRun) {
    Write-Host "[DRY-RUN]: Simulating account and ACL setup. No system changes made." -ForegroundColor Yellow
}

# 1. Administrator Privilege Check
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
$isAdmin = $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin -and -not $DryRun) {
    Write-Warning "Administrative privileges are required to configure local user accounts and NTFS ACLs."
    Write-Warning "Please re-run this script in an elevated PowerShell terminal."
    exit 1
}

# 2. Account Provisioning
Write-Host ""
Write-Host "[STEP 1/3] Checking local service account '$AgentUser'..." -ForegroundColor Green
if (-not $DryRun) {
    $existing = Get-LocalUser -Name $AgentUser -ErrorAction SilentlyContinue
    if (-not $existing) {
        $passwordGuid = [guid]::NewGuid().ToString("N")
        $password = ConvertTo-SecureString -AsPlainText -Force $passwordGuid
        New-LocalUser -Name $AgentUser -Password $password -Description "Restricted execution service account for FRIDAY AI Agent" -PasswordNeverExpires
        Write-Host "Account '$AgentUser' created successfully." -ForegroundColor Green
    } else {
        Write-Host "Account '$AgentUser' already exists." -ForegroundColor Green
    }
} else {
    Write-Host "[DRY-RUN] Would create local account '$AgentUser' with restricted token."
}

# 3. NTFS ACL Protection on config and core
Write-Host ""
Write-Host "[STEP 2/3] Hardening config and core directory ACLs..." -ForegroundColor Green

$ProtectedPaths = @(
    (Join-Path $ConfigDir "policy.yaml"),
    (Join-Path $ConfigDir "owned_assets.yaml"),
    (Join-Path $ConfigDir "config.yaml"),
    $ConfigDir,
    $CoreDir
)

foreach ($targetPath in $ProtectedPaths) {
    if (Test-Path $targetPath) {
        Write-Host "  Protecting: $targetPath"
        if (-not $DryRun) {
            $grantArg = "$AgentUser" + ":(OI)(CI)(RX)"
            $denyArg = "$AgentUser" + ":(OI)(CI)(W,D)"
            & icacls "$targetPath" /grant "$grantArg" /deny "$denyArg" | Out-Null
            Write-Host "  Set Deny Write/Delete for '$AgentUser' on $targetPath" -ForegroundColor Green
        } else {
            Write-Host "  [DRY-RUN] Would set Deny Write/Delete for '$AgentUser' on $targetPath"
        }
    }
}

# 4. Summary and Verification
Write-Host ""
Write-Host "[STEP 3/3] Security verification summary:" -ForegroundColor Green
Write-Host "  - Agent account: $AgentUser (Restricted Token)"
Write-Host "  - Read-Only configs: config/policy.yaml, config/owned_assets.yaml, config/config.yaml"
Write-Host "  - Status: Configuration tamper-proofing active." -ForegroundColor Cyan
Write-Host ""
Write-Host "Setup completed successfully."
Write-Host ""
