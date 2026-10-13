$targetPath = ".\justcells2d_brightfield_1\justcells2d_brightfield_1_MMStack_Pos0_microsam_tile512_frames";
$totalFiles = 75;

$startTime = Get-Date;
$lastCount = 0;
$lastTime = Get-Date;
$speed = 0;

do {
    $files = Get-ChildItem -Path $targetPath -File -Filter *.tif;
    $currentCount = $files.Count;
    $now = Get-Date;
    
    $elapsedInterval = ($now - $lastTime).TotalSeconds;
    if ($currentCount -gt $lastCount -and $elapsedInterval -gt 0) {
        $speed = ($currentCount - $lastCount) / $elapsedInterval;
        $lastCount = $currentCount;
        $lastTime = $now;
    }

    $percent = [math]::Min([math]::Round(($currentCount / $totalFiles) * 100), 100);
    $remainingFiles = $totalFiles - $currentCount;

    if ($speed -gt 0) {
        $etaSeconds = [math]::Round($remainingFiles / $speed);
        $etaTime = New-TimeSpan -Seconds $etaSeconds;
        $etaString = $etaTime.ToString("hh\:mm\:ss");
        $ratePerMin = [math]::Round($speed * 60, 2);
        $statusText = "$currentCount / $totalFiles files ($percent%) | $ratePerMin files/min | ETA: $etaString";
    } else {
        $statusText = "$currentCount / $totalFiles files ($percent%) | Calculating speed & ETA...";
    }

    Write-Progress -Activity "Generating MicroSAM Tile Frames" -Status $statusText -PercentComplete $percent;

    Start-Sleep -Seconds 3;
} while ($currentCount -lt $totalFiles);

Write-Progress -Activity "Generating MicroSAM Tile Frames" -Completed;
$totalTime = (Get-Date) - $startTime;
Write-Host "Done! $totalFiles files processed in $($totalTime.ToString("hh\:mm\:ss"))." -ForegroundColor Green;