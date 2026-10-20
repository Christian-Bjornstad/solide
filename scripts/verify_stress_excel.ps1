param([string]$RunDirectory)
$ErrorActionPreference='Stop'
if(-not $RunDirectory){
    $RunDirectory=Get-Content -LiteralPath (Join-Path $PSScriptRoot '../artifacts/stress/latest.txt') -Raw
}
$excel=$null
$book=$null
$results=@()
try {
    $excel=New-Object -ComObject Excel.Application
    $excel.Visible=$false
    $excel.DisplayAlerts=$false
    $excel.AskToUpdateLinks=$false
    $excel.AutomationSecurity=3
    foreach($report in Get-ChildItem -LiteralPath $RunDirectory -Filter '*.xlsx') {
        $book=$excel.Workbooks.Open($report.FullName,0,$true)
        if($book.RepairMode){throw 'Excel repair mode was required'}
        $raw=$book.Worksheets.Item('Rådata')
        if($raw.UsedRange.Rows.Count -ne 13){throw 'Original rows are missing'}
        if($raw.UsedRange.HasFormula -ne $false){throw 'Original data contains an executable formula'}
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($raw)
        $results+=[PSCustomObject]@{report=$report.Name;opened_without_repair=$true;original_rows=12;formulas=$false}
        $book.Close($false)
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($book)
        $book=$null
    }
    if($results.Count -ne 7){throw 'Expected seven synthetic reports from the complete stress run'}
    $results | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath (Join-Path $RunDirectory 'native-excel.json') -Encoding UTF8
    [PSCustomObject]@{reports=$results.Count;opened_without_repair=$true;original_rows_preserved=$true;formulas=$false} | ConvertTo-Json -Compress
} finally {
    if($null -ne $book){$book.Close($false);[void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($book)}
    if($null -ne $excel){$excel.Quit();[void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($excel)}
}
