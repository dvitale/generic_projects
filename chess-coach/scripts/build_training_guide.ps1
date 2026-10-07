# Rebuild the standalone guide with PowerShell 7. No assets or network required.
$guideRoot = Split-Path -Parent $PSScriptRoot
$guideBody = (ConvertFrom-Markdown -Path (Join-Path $guideRoot 'docs/training-guide.md')).Html
$guideLinks = [regex]::Matches($guideBody, '<h2 id="([^"]+)">(.*?)</h2>') | ForEach-Object { '<a href="#' + $_.Groups[1].Value + '">' + $_.Groups[2].Value + '</a>' }
$guideBody = [regex]::Replace($guideBody, '<a href="(https?://[^"]+)"', '<a target="_blank" rel="noopener noreferrer" href="$1"')
$guideTemplate = @'
<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<title>Guida di allenamento · SparringMate</title>
<style>
:root{font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#20372e;background:#f5f6f1;line-height:1.7;scroll-behavior:smooth}
*{box-sizing:border-box}body{margin:0}a{color:#256746;text-underline-offset:.2em}a:hover{color:#123d2a}button{font:inherit;cursor:pointer}a:focus-visible,button:focus-visible{outline:3px solid #b97712;outline-offset:4px}
.skip{position:absolute;left:16px;top:-80px;background:white;padding:12px;z-index:5}.skip:focus{top:12px}
header{background:#183d30;color:#fff;padding:24px max(24px,calc((100vw - 1240px)/2));display:flex;justify-content:space-between;align-items:center;gap:20px}header strong{font-size:1.4rem;letter-spacing:-.04em}header small{display:block;color:#c6dacc}header button{background:#edf4e7;border:0;border-radius:8px;padding:8px 16px;color:#183d30}
.layout{max-width:1240px;margin:auto;display:grid;grid-template-columns:240px minmax(0,1fr);gap:40px;padding:36px 24px 64px}aside{align-self:start;position:sticky;top:24px;max-height:calc(100vh - 48px);overflow:auto}aside p{font-weight:700;font-size:.75rem;text-transform:uppercase;letter-spacing:.12em;color:#526459;margin:0 0 12px}nav{display:grid;gap:6px}nav a{display:block;text-decoration:none;font-size:.94rem;padding:10px 12px;border-radius:8px;line-height:1.4}nav a:hover{background:#e6ecdf}
main{min-width:0;background:#fff;padding:36px 44px;border:1px solid #dfe5da;border-radius:16px;box-shadow:0 6px 25px #24432d07}h1,h2,h3{line-height:1.22;letter-spacing:-.025em;text-wrap:balance}h1{font-size:clamp(1.9rem,4vw,2.7rem);margin:0 0 24px;color:#173c2b}h2{font-size:1.6rem;margin:50px 0 20px;padding-top:28px;border-top:1px solid #dfe5da;scroll-margin-top:24px}h3{font-size:1.12rem;margin:30px 0 14px}p{margin:0 0 18px}h1+p{font-size:.85rem;color:#637269}li{padding-left:4px;margin:10px 0}ol,ul{padding-left:24px}strong{font-weight:650}main a{overflow-wrap:anywhere}table{border-collapse:collapse;display:block;overflow-x:auto;max-width:100%;font-size:.9rem;margin:22px 0 28px}th,td{text-align:left;border:1px solid #dce4d7;padding:12px 14px;vertical-align:top}th{background:#edf3e7}tr:nth-child(even) td{background:#f8faf5}footer{font-size:.85rem;color:#617266;border-top:1px solid #dfe5da;margin-top:36px;padding-top:20px}
@media(max-width:760px){header{padding:18px 20px;flex-wrap:wrap}.layout{display:block;padding:20px 14px 36px}aside{position:static;max-height:none;margin-bottom:24px}nav{grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}nav a{background:#e9eee3;font-size:.85rem;padding:10px}main{padding:26px 20px;border-radius:12px}h2{font-size:1.4rem}th,td{padding:9px}header small{font-size:.8rem}}
@media(prefers-reduced-motion:reduce){:root{scroll-behavior:auto}}
@media print{:root{background:white;color:#111;font-size:10pt}header{padding:0 0 15px;background:white;color:#111}header small,header button,aside,.skip{display:none}.layout{display:block;padding:0}main{padding:0;border:0;box-shadow:none}h2,h3{break-after:avoid}h2{margin-top:24px;padding-top:18px}table{display:table;width:100%;overflow:visible}tr{break-inside:avoid}a{color:inherit;text-decoration:none}}
</style>
</head>
<body>
<a class="skip" href="#contenuto">Vai al contenuto</a>
<header><div><strong>SparringMate</strong><small>Una guida pratica per allenarti contro Maia</small></div><button type="button" onclick="window.print()">Stampa / Salva PDF</button></header>
<div class="layout"><aside><p>In questa guida</p><nav aria-label="Indice della guida">{{NAV}}</nav></aside>
<main id="contenuto">{{CONTENT}}<footer>Guida personale SparringMate · Disponibile anche offline dopo il download. I collegamenti ai servizi esterni richiedono Internet.</footer></main></div>
</body>
</html>
'@
$guideHtml = $guideTemplate.Replace('{{NAV}}', ($guideLinks -join "`n")).Replace('{{CONTENT}}', $guideBody).Replace("`r`n", "`n")
[System.IO.File]::WriteAllText((Join-Path $guideRoot 'docs/training-guide.html'), $guideHtml.TrimEnd()+"`n", [System.Text.UTF8Encoding]::new($false))
