param(
  [Parameter(Mandatory=$true)][string]$ScriptJson,
  [Parameter(Mandatory=$true)][string]$OutputDir
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$scenes = Get-Content -Raw -Encoding UTF8 -Path $ScriptJson | ConvertFrom-Json
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.SelectVoice('Microsoft Zira Desktop')
$synth.Rate = 0
try {
  foreach ($scene in $scenes) {
    $filename = Join-Path $OutputDir ('voice_{0:D2}.wav' -f [int]$scene.index)
    $synth.SetOutputToWaveFile($filename)
    $synth.Speak([string]$scene.voice)
    $synth.SetOutputToNull()
    Write-Output ('Rendered {0:D2}: {1}' -f [int]$scene.index, [string]$scene.title)
  }
} finally {
  $synth.Dispose()
}
