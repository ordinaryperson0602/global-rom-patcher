"""상수 정의"""

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

# 모델 로더 매핑은 paths.py에서 정의됨 (LOADER_FILES)
# 순환 참조 방지를 위해 함수로 제공
def get_model_loader(model: str) -> str:
    """
    모델에 해당하는 로더 파일 경로 반환
    
    Args:
        model: 모델명 ("TB520FU", "TB710FU", "TB321FU")
        
    Returns:
        로더 파일 경로 (Path 또는 str)
    """
    from config.paths import LOADER_FILES
    return LOADER_FILES.get(model)


def get_model_config() -> dict:
    """
    모델 설정 반환 (이름 + 로더)
    
    Returns:
        {
            "TB520FU": {"name": "TB520FU(Yoga Pad pro)", "loader": "..."},
            ...
        }
    """
    from config.paths import LOADER_FILES
    return {
        model: {
            "name": MODEL_INFO[model],
            "loader": LOADER_FILES[model]
        }
        for model in MODEL_INFO.keys()
    }

# UI 상수
class UIConstants:
    """UI 관련 상수"""
    ICON_ERROR = 16      # 에러 아이콘 (X)
    ICON_WARNING = 48    # 경고 아이콘 (!)
    ICON_INFO = 64       # 정보 아이콘 (i)

# 타이밍 상수
class TimingConstants:
    """시간 지연 관련 상수"""
    EDL_BOOT_WAIT = 6    # EDL 모드 전환 대기 시간(초)

# 파일/폴더 관련 상수
class FileConstants:
    """파일명 및 확장자 관련 상수"""
    # 이미지 파일명
    VBMETA_IMG = "vbmeta.img"
    VBMETA_SYSTEM_IMG = "vbmeta_system.img"
    BOOT_IMG = "boot.img"
    VENDOR_BOOT_IMG = "vendor_boot.img"
    
    # 파티션 이미지들
    PERSIST_IMG = "persist.img"
    DEVINFO_IMG = "devinfo.img"
    KEYSTORE_IMG = "keystore.img"
    
    # 백업 확장자
    BACKUP_EXTENSION = ".original"
    BACKUP_EXTENSION_OLD = ".original_old"
    
    # 정보 파일
    INFO_TXT = "info.txt"
    CUSTOM_ROM_INFO_TXT = "custom_rom_info.txt"
    
    # 임시 파일
    TEMP_BOOT_IMG = "boot_temp.img"
    TEMP_VBMETA_SYSTEM_IMG = "vbmeta_system_temp.img"

class FolderConstants:
    """폴더명 관련 상수"""
    IMAGE_DIR = "image"           # 롬 파일 내 이미지 폴더
    RAW_SUFFIX = "_RAW"           # RAW 백업 폴더 접미사
    PATCHED_SUFFIX = "_patched"   # 패치된 폴더 접미사
    
class PartitionConstants:
    """파티션 관련 상수"""
    # 모든 파티션 목록
    ALL_PARTITIONS = ['vbmeta_system', 'vbmeta', 'vendor_boot', 'boot', 
                     'persist', 'devinfo', 'keystore']
    
    # 백업 대상 파티션
    BACKUP_PARTITIONS = ['persist', 'devinfo', 'keystore']
    
    # 슬롯 A/B
    SLOT_A = "_a"
    SLOT_B = "_b"

class ValidationConstants:
    """검증 관련 상수"""
    MAX_FOLDER_DEPTH = 3          # 폴더 구조 검색 최대 깊이
    MAX_RETRY_ATTEMPTS = 3        # 재시도 최대 횟수
    
class CodeConstants:
    """코드 품질 관련 상수"""
    MAX_FUNCTION_LINES = 150      # 함수 최대 라인 수

