# GPT-SoVITS 자동 설치 스크립트 (Windows)
# - PC 사양 확인 -> 맞는 공식 패키지 다운로드 -> 압축 해제 -> 바탕화면 실행 파일 생성 -> WebUI 실행
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$Desktop    = [Environment]::GetFolderPath('Desktop')
$LogFile    = Join-Path $Desktop 'GPT-SoVITS-설치기록.txt'
$InstallDir = 'C:\AI'   # 경로에 한글/공백이 있으면 GPT-SoVITS가 오작동하므로 C:\AI 사용
$BaseUrl    = 'https://huggingface.co/lj1995/GPT-SoVITS-windows-package/resolve/main'

function Log($msg) {
    $line = "[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $msg
    Write-Host $line
    Add-Content -Path $LogFile -Value $line -Encoding UTF8
}

Set-Content -Path $LogFile -Value "GPT-SoVITS 설치 기록 - $(Get-Date)" -Encoding UTF8

try {
    # ---------- 1. PC 사양 ----------
    Log '=== 1단계: PC 사양 확인 ==='
    $os  = Get-CimInstance Win32_OperatingSystem
    $cs  = Get-CimInstance Win32_ComputerSystem
    $cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
    $ramGB = [math]::Round($cs.TotalPhysicalMemory / 1GB, 1)
    Log ("OS: {0} (빌드 {1})" -f $os.Caption, $os.BuildNumber)
    Log ("CPU: {0}" -f $cpu.Name.Trim())
    Log ("RAM: {0} GB" -f $ramGB)

    $gpus = Get-CimInstance Win32_VideoController
    foreach ($g in $gpus) { Log ("그래픽카드: {0} (드라이버 {1})" -f $g.Name, $g.DriverVersion) }

    $nvName = $null; $nvVramGB = $null
    $smi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
    if (-not $smi -and (Test-Path 'C:\Windows\System32\nvidia-smi.exe')) { $smi = 'C:\Windows\System32\nvidia-smi.exe' }
    if ($smi) {
        $q = & $smi --query-gpu=name,memory.total,driver_version --format=csv,noheader,nounits 2>$null | Select-Object -First 1
        if ($q) {
            $parts = $q.Split(',') | ForEach-Object { $_.Trim() }
            $nvName = $parts[0]; $nvVramGB = [math]::Round([double]$parts[1] / 1024, 1)
            Log ("NVIDIA GPU: {0} / VRAM {1} GB / 드라이버 {2}" -f $nvName, $nvVramGB, $parts[2])
        }
    }

    $drive = Get-PSDrive -Name C
    $freeGB = [math]::Round($drive.Free / 1GB, 1)
    Log ("C 드라이브 여유 공간: {0} GB" -f $freeGB)

    # ---------- 2. 설치 가능 여부 판단 ----------
    Log '=== 2단계: 설치 조건 확인 ==='
    if (-not $nvName) {
        Log '경고: NVIDIA 그래픽카드를 찾지 못했습니다. 설치는 되지만 CPU로 돌아가서 매우 느리고, 내 목소리 학습은 사실상 어렵습니다.'
        $ans = Read-Host '그래도 계속 설치할까요? (y/n)'
        if ($ans -ne 'y') { Log '사용자가 설치를 중단했습니다.'; exit 1 }
    } elseif ($nvVramGB -lt 4) {
        Log "경고: VRAM이 $nvVramGB GB로 4GB보다 적습니다. 음성 생성이 느리거나 CPU로 돌아갈 수 있습니다."
    } elseif ($nvVramGB -lt 8) {
        Log "참고: VRAM $nvVramGB GB - 음성 생성은 충분, 학습은 배치 크기를 줄여야 할 수 있습니다."
    } else {
        Log "VRAM $nvVramGB GB - 음성 생성/학습 모두 충분합니다."
    }

    if ($freeGB -lt 30) {
        Log "오류: C 드라이브 여유 공간이 $freeGB GB입니다. 다운로드+압축 해제에 약 30GB가 필요합니다. 공간을 확보한 뒤 다시 실행해 주세요."
        exit 1
    }

    # RTX 50 시리즈는 전용 패키지
    if ($nvName -and $nvName -match 'RTX\s*50\d\d') {
        $pkg = 'GPT-SoVITS-v2pro-20250604-nvidia50.7z'; $pkgSize = '8.84GB'
    } else {
        $pkg = 'GPT-SoVITS-v2pro-20250604.7z'; $pkgSize = '8.19GB'
    }
    Log "선택한 패키지: $pkg ($pkgSize, 공식 Hugging Face 저장소 lj1995/GPT-SoVITS-windows-package)"

    # ---------- 3. 다운로드 ----------
    Log '=== 3단계: 다운로드 (인터넷 속도에 따라 10분~1시간) ==='
    New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
    $archive = Join-Path $InstallDir $pkg
    $url = "$BaseUrl/$pkg`?download=true"
    # curl.exe 는 Windows 10/11 기본 포함. -C - 로 끊겨도 이어받기 가능
    & curl.exe -L --retry 5 --retry-delay 5 -C - -o $archive $url
    if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne 33) { throw "다운로드 실패 (curl 코드 $LASTEXITCODE). 이 파일을 다시 실행하면 이어서 받습니다." }
    $sizeGB = [math]::Round((Get-Item $archive).Length / 1GB, 2)
    Log "다운로드 완료: $archive ($sizeGB GB)"
    if ($sizeGB -lt 7) { throw "파일 크기가 예상보다 작습니다($sizeGB GB). 이 파일을 다시 실행하면 이어서 받습니다." }

    # ---------- 4. 압축 해제 ----------
    Log '=== 4단계: 압축 해제 (5~15분) ==='
    $sevenZip = @("$env:ProgramFiles\7-Zip\7z.exe", "${env:ProgramFiles(x86)}\7-Zip\7z.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $sevenZip) {
        Log '7-Zip이 없어 winget으로 설치합니다.'
        try {
            & winget install --id 7zip.7zip -e --silent --accept-package-agreements --accept-source-agreements | Out-Host
        } catch { Log "winget 실행 실패: $_" }
        $sevenZip = @("$env:ProgramFiles\7-Zip\7z.exe", "${env:ProgramFiles(x86)}\7-Zip\7z.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
    }
    if ($sevenZip) {
        Log "7-Zip으로 압축 해제: $sevenZip"
        & $sevenZip x $archive "-o$InstallDir" -aoa -y | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "7-Zip 압축 해제 실패 (코드 $LASTEXITCODE)" }
    } else {
        Log 'Windows 기본 tar로 압축 해제를 시도합니다.'
        & tar.exe -xf $archive -C $InstallDir
        if ($LASTEXITCODE -ne 0) { throw '압축 해제 실패. 7-Zip(https://www.7-zip.org)을 설치한 뒤 이 파일을 다시 실행해 주세요.' }
    }

    $appDir = Get-ChildItem $InstallDir -Directory | Where-Object { Test-Path (Join-Path $_.FullName 'go-webui.bat') } | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $appDir) { throw 'go-webui.bat 를 찾지 못했습니다. 압축 해제가 제대로 되지 않았습니다.' }
    Log "설치 폴더: $($appDir.FullName)"

    # ---------- 5. 바탕화면 실행 파일 ----------
    Log '=== 5단계: 바탕화면 실행 파일 만들기 ==='
    $launcher = Join-Path $Desktop 'GPT-SoVITS 실행.bat'
    $bat = "@echo off`r`ncd /d `"$($appDir.FullName)`"`r`ncall go-webui.bat`r`n"
    [System.IO.File]::WriteAllText($launcher, $bat, (New-Object System.Text.UTF8Encoding($false)))
    Log "만듦: $launcher"

    Log '=== 설치 완료! WebUI를 실행합니다. 잠시 후 브라우저에 http://localhost:9874 가 열립니다. ==='
    Log "참고: 다운로드한 압축파일($archive, 약 $sizeGB GB)은 지워도 됩니다."
    Start-Process -FilePath (Join-Path $appDir.FullName 'go-webui.bat') -WorkingDirectory $appDir.FullName
}
catch {
    Log "오류 발생: $($_.Exception.Message)"
    Log '이 창을 캡처하거나 Claude에게 "설치 오류 났어"라고 말해 주세요.'
    exit 1
}
