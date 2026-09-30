$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
$checks = 0
function Assert-Source([bool] $Condition, [string] $Message) {
    if (!$Condition) { throw $Message }
    $script:checks++
}
function Read-Source([string] $RelativePath) {
    Get-Content -LiteralPath (Join-Path $repo $RelativePath) -Raw
}

# Source-contract checks, not an emulation of Papyrus or the game engine.
$model = Read-Source 'dist/Source/Scripts/sslThreadModel.psc'
$animation = Read-Source 'src/Thread/ThreadAnimation.cpp'
$thread = Read-Source 'src/Thread/Thread.cpp'
$overlay = Read-Source 'src/Thread/Interface/Elements/AnimSpeedOverlay.cpp'
$contracts = @{
    ContinueSetup = 'bool abContinue, int aiRequest = 0'
    OnNativeActorRecoveryComplete = 'bool abSucceeded, int aiRequest = 0'
    OnPlayerSheatheComplete = 'bool abSucceeded, int aiRequest = 0'
    OnPlayerDialogueComplete = 'int aiRequest = 0'
    OnNativeActorsPrepared = 'int aiRequest = 0'
    OnAnimationSyncFailed = 'int aiRequest = 0'
    OnAnimationSynchronized = 'int aiRequest = 0'
    OnFixedLengthStageComplete = 'int aiRequest = 0'
}
foreach ($name in $contracts.Keys) {
    $declarations = [regex]::Matches($model, ('(?im)^\s*Function\s+' + $name + '\(([^)]*)\)'))
    Assert-Source ($declarations.Count -eq 2) "$name must have state and fallback declarations"
    foreach ($declaration in $declarations) {
        Assert-Source ($declaration.Groups[1].Value -eq $contracts[$name]) "$name signature mismatch"
    }
    $calls = [regex]::Matches(($animation + $thread), ('DispatchMethodCall\([^\r\n]*"' + $name + '"[^\r\n]*'))
    Assert-Source ($calls.Count -gt 0) "$name has no native dispatch"
    foreach ($call in $calls) {
        Assert-Source ($call.Value -match 'int32_t\{ (startupRequest|a_request) \}') "$name dispatch lacks request token"
    }
}
Assert-Source ($overlay -match '"UpdateBaseSpeedFromPlayback"[^\r\n]*GetStartupRequest\(\)') 'Speed UI callback lacks request token'
Assert-Source ($model -match 'Function UpdateBaseSpeedFromPlayback\(float afPlaybackSpeed, int aiRequest = 0, int aiSequence = 0\)') 'Speed callback signature mismatch'
Assert-Source ($overlay -match 'int32_t\{ sequence \}') 'Speed dispatch lacks operation sequence'
Assert-Source ($model -match 'CommitPlaybackBase\(baseSpeed, request, aiSequence\)') 'Sequenced speed callback bypasses native commit'
$native = Read-Source 'src/Papyrus/sslThreadModel.cpp'
$commit = [regex]::Match($native, '(?s)void CommitPlaybackBase\(.*?(?=bool RestartFixedLengthTimer)').Value
Assert-Source ($commit -match 'IsStartupRequest\(a_request\).*IsCurrentSpeedRequest\(a_sequence\)') 'Speed commit lacks request/sequence validation'
Assert-Source ($commit.IndexOf('IsCurrentSpeedRequest') -lt $commit.IndexOf('PackValue(base')) 'Speed commit validates too late'
$alias = Read-Source 'dist/Source/Scripts/sslActorAlias.psc'
$prepare = [regex]::Match($alias, '(?s)Event OnDoPrepare\(.*?EndEvent').Value
Assert-Source ($prepare -match 'int request = asStringArg as int') 'Preparation event uses receiver token instead of sender token'
Assert-Source ($prepare.IndexOf('request != _Thread.StartupRequest') -lt $prepare.IndexOf('UnregisterForModEvent')) 'Stale preparation event can remove current listener'
Assert-Source ($model.Contains('SendModEvent("SSL_PREPARE_Thread" + tid, request as string)')) 'Preparation sender omits request token'

$slots = Read-Source 'dist/Source/Scripts/sslAnimationSlots.psc'
foreach ($name in @('SyncBackEnd', 'EnsureBackEnd')) {
    $body = [regex]::Match($slots, ('(?s)Function ' + $name + '\(\)(.*?)EndFunction')).Groups[1].Value
    Assert-Source ($body -match '(?s)If \(!aliases.Length\).*?return.*?EndIf\s+String\[\] ids = CreateProxyArray') "$name treats zero aliases as an unlimited query"
}
Assert-Source ($slots -match '(?s)If \(ProxyIdsMatch\(_proxyid, ids\)\).*?BindProxyAliases\(aliases, ids, true\).*?return') 'Proxy cache hit skips actual alias validation'

$ctor = Read-Source 'src/Thread/ThreadCtor.cpp'
$center = [regex]::Match($ctor, '(?s)Instance::InitializeCenter\(.*?(?=bool Instance::InitializeFixedCenter)').Value
Assert-Source ($center.Length -gt 0) 'Center initializer not found'
Assert-Source ($center -match 'std::promise<void> promise') 'Center initializer has unexpected completion contract'
$afterWait = $center.Substring($center.IndexOf('future.get();'))
Assert-Source ($afterWait -notmatch 'center.SetReference|InitializeCenterRefMenu') 'Center initializer writes aliases on worker after wait'
$updating = $animation.Substring($animation.IndexOf('void Instance::UpdatePendingAnimations('))
Assert-Source ($updating.IndexOf('playerDialoguePending && IsPlayerDialogueActive()') -lt $updating.IndexOf('startupElapsed += a_delta')) 'Dialogue wait consumes native preparation timeout'
Assert-Source ($model -match '_preparationStartedAt >= 0.0 && GetStartupClock\(\) - _preparationStartedAt >= 60.0') 'Papyrus timeout ignores dialogue-wait sentinel'
$registration = Read-Source 'src/Papyrus/sslThreadModel.h'
foreach ($name in @('GetActiveScene', 'GetActiveStage', 'GetPlayingScenes', 'GetPositions', 'SelectNextStage', 'CommitPlaybackBase',
        'DestroyInstance', 'CancelPendingAnimations', 'InitSceneHUDImpl', 'DestroySceneHUDImpl',
        'SetFocusSceneHUDImpl', 'UpdateMenuTimerDisplay', 'OnStageChangedUpdateHUD',
        'EnjBarsChangeHighlightedPartner', 'OpenStageSelectMenuImpl', 'SetVisibilitySceneGraphImpl')) {
    Assert-Source ($registration.Contains(('REGISTERFUNC({0}, "sslThreadModel", false);' -f $name))) "$name may run on a Papyrus tasklet"
}
Write-Output "PASS: $checks source-contract checks (not game-runtime tests)"
