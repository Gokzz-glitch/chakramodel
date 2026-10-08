$base = "J:\My Drive\DATASET FOR CHAKRAMODEL BY ANTI\PolypGen\extracted\PolypGen2021_MultiCenterData_v3"

Write-Host "=== Direct Children of PolypGen2021_MultiCenterData_v3 ==="
$children = Get-ChildItem -LiteralPath $base -Force
foreach ($c in $children) {
    if ($c.PSIsContainer) {
        $files = (Get-ChildItem -LiteralPath $c.FullName -Recurse -File -Force).Count
        $dirs = (Get-ChildItem -LiteralPath $c.FullName -Recurse -Directory -Force).Count
        Write-Host ("DIR:  {0,-35} | Subdirs: {1,5} | Files: {2,6}" -f $c.Name, $dirs, $files)
    } else {
        Write-Host ("FILE: {0,-35} | Size: {1,12} bytes" -f $c.Name, $c.Length)
    }
}

