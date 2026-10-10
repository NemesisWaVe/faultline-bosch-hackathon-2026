# EMERGENCY STOP — undo every possible fault on every shop container.
# Plain English: the big red button. Safe to run any time, even if nothing is broken.
# Run:  powershell -ExecutionPolicy Bypass -File chaos\stop_all.ps1

$project = "opentelemetry-demo"
$tcImage = "ghcr.io/alexei-led/pumba-alpine-nettools:latest"

Write-Host "1) Stopping any running Pumba network-fault helpers..."
docker ps -q --filter "name=chaos-netem-" | ForEach-Object { docker stop $_ | Out-Null }

$containers = docker ps -a --filter "label=com.docker.compose.project=$project" --format "{{.Names}}|{{.State}}"
foreach ($line in $containers) {
    $name, $st = $line -split "\|"
    if ($st -eq "paused") {
        Write-Host "2) Unfreezing $name"; docker unpause $name | Out-Null
    } elseif ($st -eq "exited" -or $st -eq "dead" -or $st -eq "created") {
        Write-Host "2) Starting $name";   docker start $name | Out-Null
    }
}

Write-Host "3) Removing leftover network delay rules (harmless if none exist)..."
foreach ($line in $containers) {
    $name = ($line -split "\|")[0]
    docker run --rm --net "container:$name" --cap-add NET_ADMIN $tcImage tc qdisc del dev eth0 root 2>$null | Out-Null
}

Write-Host "4) Final state:"
docker ps -a --filter "label=com.docker.compose.project=$project" --format "table {{.Names}}\t{{.Status}}"
