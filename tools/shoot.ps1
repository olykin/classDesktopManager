param(
  [string]$Scene = "bubble",
  [int]$ShotMs = 5000,
  [int]$Life = 14000,
  [string]$Out = "D:\tixing\_scratch\shot.png"
)
$py = 'C:\Users\iflytek\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\pythonw.exe'
$env:DSR_LIFE = "$Life"
$env:PYTHONIOENCODING = 'utf-8'
$log = 'D:\tixing\_scratch\visual.log'
$p = Start-Process -FilePath $py -ArgumentList @('D:\tixing\tools\visual_check.py', $Scene) -PassThru -RedirectStandardError $log -RedirectStandardOutput 'D:\tixing\_scratch\visual.out'
Start-Sleep -Milliseconds $ShotMs
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
$b = [System.Windows.Forms.SystemInformation]::VirtualScreen
$bmp = New-Object System.Drawing.Bitmap($b.Width, $b.Height)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($b.Left, $b.Top, 0, 0, $bmp.Size)
$bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose(); $bmp.Dispose()
Write-Output "saved $Out"
$p | Wait-Process -Timeout 40 -ErrorAction SilentlyContinue
