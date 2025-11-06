"""통합 설정 파일 - colors, constants, messages 통합"""
import os
import sys
import platform
import shutil
from pathlib import Path
from functools import lru_cache

# ============================================================================
# COLORS (원래 config/colors.py)
# ============================================================================

# Windows에서 ANSI 색상 활성화
if platform.system() == "Windows":
    os.system("")

class Colors:
    """ANSI 색상 코드"""
    HEADER = '\033[94m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


# ============================================================================
# CONSTANTS (원래 config/constants.py)
# ============================================================================

# 버전 정보
APP_VERSION = "1.0.0"
APP_NAME = "Global ROM Patcher"
APP_AUTHOR = "Ordinary_Person"
APP_LAST_UPDATED = "2025-11-04"

# Hex 코드
HEX_PRC = b'\x00\x2E\x50\x52\x43\x00'
HEX_IPRC = b'\x00\x49\x50\x52\x43\x00'
HEX_ROW = b'\x00\x2E\x52\x4F\x57\x00'
HEX_IROW = b'\x00\x49\x52\x4F\x57\x00'

# GKI 설정
GKI_OWNER = "WildKernels"
GKI_REPO = "GKI_KernelSU_SUSFS"
GKI_TAG = "v1.5.9-r36"
GKI_REPO_URL = f"https://github.com/{GKI_OWNER}/{GKI_REPO}"

# KernelSU Manager
KSU_MANAGER_REPO = "KernelSU-Next/KernelSU-Next"
KSU_MANAGER_TAG = "v1.1.1"

# 모델 정보
MODEL_INFO = {
    "TB520FU": "TB520FU(Yoga Pad pro)",
    "TB710FU": "TB710FU(Xiaoxin Pad Pro GT)",
    "TB321FU": "TB321FU(Legion Y700 3rd)"
}

# UI 상수
class UIConstants:
    """UI 관련 상수"""
    ICON_INFO = "INFO"
    ICON_WARNING = "WARNING"
    ICON_ERROR = "ERROR"
    ICON_QUESTION = "QUESTION"

# 폴더 상수
class FolderConstants:
    """폴더 이름 상수"""
    IMAGE_FOLDER = "image"
    RAW_SUFFIX = "_RAW"

# 파일 상수
class FileConstants:
    """파일 이름 상수"""
    VBMETA = "vbmeta.img"
    VBMETA_SYSTEM = "vbmeta_system.img"
    VENDOR_BOOT = "vendor_boot.img"
    BOOT = "boot.img"

# 검증 상수
class ValidationConstants:
    """검증 관련 상수"""
    MAX_ROM_FOLDER_COUNT = 10
    MIN_ROM_SIZE_MB = 1


# ============================================================================
# MESSAGES (원래 config/messages.py)
# ============================================================================

class ErrorMessages:
    """에러 메시지"""
    
    # EDL 관련
    EDL_DISCONNECT = "EDL 모드 중 PC와 태블릿의 통신에 문제가 생겼습니다."
    EDL_DISCONNECT_DETAIL = (
        "EDL 모드 중 PC와 태블릿의 통신에 문제가 생겼습니다.\n\n"
        "PC와 태블릿의 연결을 해제하고,\n"
        "볼륨 다운 + 전원 버튼을 15초가량 눌러\n"
        "강제 재부팅한 후 프로그램을 다시 실행하십시오."
    )
    EDL_LOADER_NOT_SET = "로더 파일이 설정되지 않았습니다."
    EDL_LOADER_NOT_FOUND = "로더 파일을 찾을 수 없습니다."
    EDL_MODE_ENTRY_FAILED = "EDL 모드 진입 실패"
    EDL_CONNECTION_FAILED = "EDL 연결 확인 실패"
    
    # 모델 관련
    MODEL_UNSUPPORTED = "지원되지 않는 모델입니다.\n확인된 모델: {model}"
    MODEL_MISMATCH = "ADB로 확인된 모델({adb_model})과\nvbmeta의 Prop 모델({vbmeta_model})이 일치하지 않습니다."
    MODEL_LOADER_NOT_FOUND = "모델({model})은(는) 확인되었으나, 필요한 로더 파일이 없습니다:\n{loader_path}"
    
    # 지역 코드 관련
    REGION_MIXED_PRC_ROW = "vendor_boot 이미지에서 ROW/IROW와(과) PRC/IPRC이(가) 모두 발견되었습니다"
    REGION_MIXED_PRC_IPRC = "vendor_boot 이미지에서 지역코드가 PRC와 IPRC로 혼합되어 발견되었습니다."
    REGION_ROW_NOT_SUPPORTED = (
        "이 제품은 정발제품(ROW/IROW Hex)으로 확인됩니다.\n"
        "정발제품은 자동업데이트(OTA)를 이용해주세요."
    )
    REGION_NOT_FOUND = "vendor_boot 이미지에서 지역코드(ROW/IROW 또는 PRC/IPRC)를 찾을 수 없습니다."
    REGION_PATTERN_NOT_FOUND = (
        "vendor_boot에서 ROW/IROW 패턴을 찾을 수 없습니다.\n\n"
        "STEP 2 검증을 통과했는데 패턴이 없다면\n"
        "파일이 손상되었거나 지원하지 않는 형식입니다."
    )
    
    # 파티션/파일 관련
    PARTITION_EXTRACTION_FAILED = "'{partition}' 파티션 추출 실패"
    PARTITION_READ_FAILED = "'{partition}' 파티션 읽기 실패"
    PARTITION_WRITE_FAILED = "'{partition}' 파티션 쓰기 실패"
    PARTITION_OPERATION_FAILED = "'{partition}' 처리 중 오류"
    FILE_ANALYSIS_FAILED = "{file} 파일 분석 중 오류: {error}"
    FILE_NOT_FOUND = "필수 파일이 없습니다.\n'Tools' 폴더를 확인하세요."
    PATCH_FILE_VERIFICATION_FAILED = "패치 파일 검증 실패"
    PATCH_CREATION_FAILED = "'{partition}' 패치 생성 실패"
    
    # vbmeta 관련
    VBMETA_FINGERPRINT_NOT_FOUND = "vbmeta Prop에서 'fingerprint' 속성을 찾을 수 없습니다."
    VBMETA_PRC_FOUND = "vbmeta에서 'PRC'(중국 롬)가 발견되었습니다.\n글로벌 롬(ROW)을 사용해주세요."
    VBMETA_PROP_MISMATCH = "vbmeta Prop에서 확인된 모델({vbmeta_model})이\n기기의 실제 모델({target_model})과 일치하지 않습니다."
    VBMETA_SIGNING_KEY_NOT_FOUND = "vbmeta 서명 키를 찾을 수 없습니다."
    
    # 롤백 관련
    ROLLBACK_INDEX_NOT_FOUND = "{partition}에서 Rollback Index를 찾을 수 없습니다."
    ROLLBACK_INDEX_LOWER = (
        "{partition} 롤백 인덱스가 기기보다 낮습니다.\n"
        "기기: {device_index}, 롬: {rom_index}\n\n"
        "이 롬으로 플래시하면 기기가 부팅하지 않습니다!"
    )
    
    # 일반 오류
    OPERATION_CANCELLED = "작업이 취소되었습니다."
    UNEXPECTED_ERROR = "예상치 못한 오류가 발생했습니다."
    TOOL_NOT_FOUND = "{tool} 도구를 찾을 수 없습니다."


class InfoMessages:
    """정보 메시지"""
    ROM_ANALYSIS_START = "롬파일 분석을 시작합니다..."
    ROM_ANALYSIS_COMPLETE = "롬파일 분석이 완료되었습니다."
    ROM_BACKUP_COMPLETE = "원본 롬파일이 백업되었습니다."
    ROM_PATCH_START = "롬파일 패치를 시작합니다..."
    ROM_PATCH_COMPLETE = "롬파일 패치가 완료되었습니다."
    
    DEVICE_INFO_EXTRACTION_START = "기기 정보 추출을 시작합니다..."
    DEVICE_INFO_EXTRACTION_COMPLETE = "기기 정보 추출이 완료되었습니다."
    
    VERIFICATION_START = "패치 검증을 시작합니다..."
    VERIFICATION_COMPLETE = "패치 검증이 완료되었습니다."
    
    COUNTRY_CODE_CHANGE_START = "국가 코드 변경을 시작합니다..."
    COUNTRY_CODE_CHANGE_COMPLETE = "국가 코드 변경이 완료되었습니다."


class TitleMessages:
    """팝업 제목 메시지"""
    ERROR = "오류"
    WARNING = "경고"
    INFO = "정보"
    SUCCESS = "성공"
    CONFIRM = "확인"


# ============================================================================
# PATHS (원래 config/paths.py) - 간소화 버전
# ============================================================================

@lru_cache(maxsize=1)
def _find_python_executable(embedded_python: Path, is_frozen: bool) -> str:
    """Python 실행 파일 찾기 (캐싱)"""
    if embedded_python.exists():
        return str(embedded_python)
    
    if is_frozen:
        found_python = shutil.which("python") or shutil.which("python3") or shutil.which("py")
        if found_python and Path(found_python).exists():
            return found_python
        
        for ver in ["312", "313", "311", "310"]:
            py_path = Path(rf"C:\Python{ver}\python.exe")
            if py_path.exists():
                return str(py_path)
        
        return "python"
    else:
        return sys.executable

# 기본 경로
if getattr(sys, 'frozen', False):
    CURRENT_DIR = Path(sys.executable).parent.resolve()
    
    if hasattr(sys, '_MEIPASS'):
        TOOL_DIR = Path(sys._MEIPASS) / "Tools"
    else:
        TOOL_DIR = CURRENT_DIR / "Tools"
    
    EMBEDDED_PYTHON = TOOL_DIR / "python_embedded" / "python.exe"
    PYTHON_EXE = _find_python_executable(EMBEDDED_PYTHON, True)
else:
    CURRENT_DIR = Path(__file__).parent.parent.resolve()
    TOOL_DIR = CURRENT_DIR / "Tools"
    
    EMBEDDED_PYTHON = TOOL_DIR / "python_embedded" / "python.exe"
    PYTHON_EXE = _find_python_executable(EMBEDDED_PYTHON, False)

# 문자열 경로
TOOLS_DIR_STR = str(TOOL_DIR)
LOADER_FILE_DIR = str(TOOL_DIR / "Loader_File")
PLATFORM_TOOLS_DIR = str(TOOL_DIR / "platform-tools")
EDL_NG_DIR = str(TOOL_DIR / "edl-ng-windows-x64")
ROOTING_TOOL_DIR = TOOL_DIR / "Rooting_Tool"
SIGNING_KEY_DIR = TOOL_DIR / "Signing_Key"
ROM_TOOLS_DIR = TOOL_DIR / "RomTools"

# RSA 폴더
RSA_BASE_DIR = Path(r"C:\Programdata\RSA")
RSA_DOWNLOAD_DIR = RSA_BASE_DIR / "Download"
RSA_ROMFILES_DIR = RSA_DOWNLOAD_DIR / "Romfiles"
ROM_DIR_STR = str(RSA_ROMFILES_DIR)

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

# 출력 디렉토리
OUTPUT_DIR = CURRENT_DIR / "Output"
ROMFILE_PATCH_BACKUP_DIR = OUTPUT_DIR / "RomFile_Patch_Backup"
COUNTRY_CODE_BACKUP_DIR = OUTPUT_DIR / "Change_CountryCode_Backup"
DEVICE_STATE_BACKUP_DIR = OUTPUT_DIR / "Device_State_Backup"
LOGS_DIR = OUTPUT_DIR / "Logs"

# 데이터 파일
STEP_DATA_FILE = str(CURRENT_DIR / "step_data.json")
CUSTOM_ROM_STEP_DATA_FILE = str(CURRENT_DIR / "custom_rom_step_data.json")

# 사용자 동의서
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    USER_AGREEMENT_FILE = Path(sys._MEIPASS) / "assets" / "프로그램_사용자_동의서.txt"
else:
    USER_AGREEMENT_FILE = CURRENT_DIR / "assets" / "프로그램_사용자_동의서.txt"


# ============================================================================
# 헬퍼 함수
# ============================================================================

def get_model_loader(model: str) -> str:
    """모델에 해당하는 로더 파일 경로 반환"""
    return LOADER_FILES.get(model)


def get_model_config() -> dict:
    """모델 설정 반환 (이름 + 로더)"""
    return {
        model: {
            "name": MODEL_INFO[model],
            "loader": LOADER_FILES[model]
        }
        for model in MODEL_INFO
    }

