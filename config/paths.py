"""경로 설정"""
import os
import sys
import shutil
from pathlib import Path

# 기본 경로 (EXE와 스크립트 모두 지원)
if getattr(sys, 'frozen', False):
    # PyInstaller로 빌드된 EXE 실행 시
    CURRENT_DIR = Path(sys.executable).parent.resolve()
    # 시스템 PATH에서 python.exe 찾기
    PYTHON_EXE = shutil.which("python") or "python"
else:
    # Python 스크립트 실행 시
    CURRENT_DIR = Path(__file__).parent.parent.resolve()
    PYTHON_EXE = sys.executable
TOOL_DIR = CURRENT_DIR / "Tools"

# 문자열 경로
TOOLS_DIR_STR = str(TOOL_DIR)
LOADER_FILE_DIR = str(TOOL_DIR / "Loader_File")
PLATFORM_TOOLS_DIR = str(TOOL_DIR / "platform-tools")
EDL_NG_DIR = str(TOOL_DIR / "edl-ng-windows-x64")
ROOTING_TOOL_DIR = TOOL_DIR / "Rooting_Tool"
SIGNING_KEY_DIR = TOOL_DIR / "Signing_Key"
ROM_TOOLS_DIR = TOOL_DIR / "RomTools"

# RSA 폴더 경로
RSA_BASE_DIR = Path(r"C:\Programdata\RSA")
RSA_DOWNLOAD_DIR = RSA_BASE_DIR / "Download"
RSA_ROMFILES_DIR = RSA_DOWNLOAD_DIR / "Romfiles"
ROM_DIR_STR = str(RSA_ROMFILES_DIR)  # 하위 호환성 유지

# 툴 경로
ADB_EXE = str(TOOL_DIR / "platform-tools" / "adb.exe")
EDL_NG_EXE = str(TOOL_DIR / "edl-ng-windows-x64" / "edl-ng.exe")
AVBTOOL_PY = str(TOOL_DIR / "avbtool.py")

# 로더 파일
LOADER_FILES = {
    "TB520FU": str(TOOL_DIR / "Loader_File" / "xbl_s_devprg_ns_TB520FU.melf"),
    "TB710FU": str(TOOL_DIR / "Loader_File" / "xbl_s_devprg_ns_TB710FU.melf"),
    "TB321FU": str(TOOL_DIR / "Loader_File" / "xbl_s_devprg_ns_TB321FU.melf")
}

# 서명 키
KNOWN_SIGNING_KEYS = {
    "2597c218aae470a130f61162feaae70afd97f011": SIGNING_KEY_DIR / "testkey_rsa4096.pem",
    "cdbb77177f731920bbe0a0f94f84d9038ae0617d": SIGNING_KEY_DIR / "testkey_rsa2048.pem"
}

# 임시 디렉토리
TEMP_WORK_DIR = CURRENT_DIR / "patch_temp"
VERIFY_TEMP_DIR = CURRENT_DIR / "verify_temp"

# 출력 디렉토리 구조
OUTPUT_DIR = CURRENT_DIR / "Output"
ROMFILE_PATCH_BACKUP_DIR = OUTPUT_DIR / "RomFile_Patch_Backup"
COUNTRY_CODE_BACKUP_DIR = OUTPUT_DIR / "Change_CountryCode_Backup"
DEVICE_STATE_BACKUP_DIR = OUTPUT_DIR / "Device_State_Backup"
LOGS_DIR = OUTPUT_DIR / "Logs"

# 데이터 파일
STEP_DATA_FILE = str(CURRENT_DIR / "step_data.json")
CUSTOM_ROM_STEP_DATA_FILE = str(CURRENT_DIR / "custom_rom_step_data.json")

