$EllaDir = "c:\Users\FOCNETH\OneDrive\Desktop\ellawcd"
Push-Location $EllaDir
try {
    if (Test-Path "$EllaDir\.venv\Scripts\python.exe") {
        & "$EllaDir\.venv\Scripts\python.exe" "$EllaDir\main.py" $args
    } else {
        python "$EllaDir\main.py" $args
    }
} finally {
    Pop-Location
}
