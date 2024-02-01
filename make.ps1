param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("help", "build", "clean")]
    [string]$target
)

# Declare variables
$PRODUCT_NAME = "Moxmoe Repacker"
$PROGRAM_NAME = "moxmoe-repacker"
$WORK_DIR = "./"
$BUILD_DIR = "./build"
$ICON_DIR = "./favicon.ico"
$MAIN_SCRIPT = "./main.py"

# Define Banner
$VERSION = (Get-Content ./.version)
$ANNOUNCE_BODY = @"

  __  __                                ____                       _             
 |  \/  | _____  ___ __ ___   ___   ___|  _ \ ___ _ __   __ _  ___| | _____ _ __ 
 | |\/| |/ _ \ \/ / '_ ` _ \ / _ \ / _ \ |_) / _ \ '_ \ / _` |/ __| |/ / _ \ '__|
 | |  | | (_) >  <| | | | | | (_) |  __/  _ <  __/ |_) | (_| | (__|   <  __/ |   
 |_|  |_|\___/_/\_\_| |_| |_|\___/ \___|_| \_\___| .__/ \__,_|\___|_|\_\___|_|   
                                                 |_|                             


Moxmoe Repacker Makefile ${VERSION}
================================================================

"@

# Declare phony targets
## Show this help message
function Make-Help {
	Write-Host "${ANNOUNCE_BODY}"
	Write-Host -ForegroundColor Cyan ("{0,-30} {1}" -f "help", "Show this help message.")
	Write-Host -ForegroundColor Cyan ("{0,-30} {1}" -f "build", "Build python project to one-file executable.")
	Write-Host -ForegroundColor Cyan ("{0,-30} {1}" -f "clean", "Clean build directory.")
}

## Build python project to one-file executable
function Make-Build {
    $NUITKA_FLAGS = @(
        "--show-scons",
        "--show-memory",
        "--show-progress",
        "--onefile", 
        "--nofollow-imports", 
        "--follow-import-to=moe_utils",
        "--output-filename=${PROGRAM_NAME}",
        "--output-dir=${BUILD_DIR}",
        "--enable-plugin=upx",
        "--windows-icon-from-ico=${ICON_DIR}",
        "--windows-product-name=${PRODUCT_NAME}",
        "--windows-file-version=${VERSION}",
        "--windows-product-version=${VERSION}",
        "${MAIN_SCRIPT}"
    )
	& python -m nuitka @NUITKA_FLAGS
}

## Clean build directory
function Make-Clean {
	Remove-Item -Recurse -Force "${BUILD_DIR}/*"
}

# 根据目标参数执行相应的操作
if ($target -eq "help") {
	Make-Help
}
elseif ($target -eq "build") {
    Make-Build
}
elseif ($target -eq "clean") {
    Make-Clean
}
