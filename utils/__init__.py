"""유틸리티 모듈"""
from .ui import show_popup, show_popup_yesno, clear_screen, get_platform_executable, is_admin
from .command import run_command, run_adb_command, run_external_command
from .region_check import check_region_patterns, validate_region_code, check_region_in_image

__all__ = [
    'show_popup', 'show_popup_yesno', 'clear_screen',
    'run_command', 'run_adb_command', 'run_external_command',
    'get_platform_executable', 'is_admin',
    'check_region_patterns', 'validate_region_code', 'check_region_in_image'
]

# 지연 로딩 (순환 참조 방지)
# country_code, backup_device는 필요할 때만 import

