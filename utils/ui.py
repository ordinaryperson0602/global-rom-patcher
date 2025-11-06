"""UI 유틸리티"""
import os
import sys
import ctypes
import platform
from pathlib import Path

def is_admin() -> bool:
    """관리자 권한 확인 (Windows)"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def show_popup(title: str, message: str, icon: int = 64, exit_on_close: bool = False) -> None:
    """Windows 팝업 표시
    
    Args:
        title: 팝업 제목
        message: 팝업 메시지
        icon: 아이콘 타입 (기본값 64=정보)
              - UIConstants.ICON_ERROR (16): 에러 아이콘 (X)
              - UIConstants.ICON_WARNING (48): 경고 아이콘 (!)
              - UIConstants.ICON_INFO (64): 정보 아이콘 (i)
        exit_on_close: True면 팝업 닫을 때 예외 발생
    """
    print(f"\n[{title}] {message}")
    try:
        ctypes.windll.user32.MessageBoxW(0, message, title, icon)
    except:
        print("(팝업 표시 실패)")
    
    if exit_on_close:
        print("프로그램을 중단합니다.")
        sys.exit(1)

def show_popup_yesno(title: str, message: str) -> int:
    """Yes/No 팝업 표시"""
    print(f"\n[확인] {title}: {message}")
    try:
        result = ctypes.windll.user32.MessageBoxW(0, message, title, 4 | 32)
        return result
    except:
        print("(팝업 표시 실패)")
        return 7

def clear_screen() -> None:
    """화면 지우기"""
    os.system('cls' if os.name == 'nt' else 'clear')

def get_platform_executable(name: str) -> Path:
    """운영체제에 맞는 도구 경로 반환"""
    from config.paths import ROOTING_TOOL_DIR
    system = platform.system()
    executables = {
        "Windows": f"{name}.exe",
        "Linux": f"{name}-linux",
        "Darwin": f"{name}-macos"
    }
    exe_name = executables.get(system)
    if not exe_name:
        raise RuntimeError(f"지원되지 않는 운영체제: {system}")
    return ROOTING_TOOL_DIR / exe_name


# Windows Console QuickEdit Mode 제어


# Windows Console Mode 플래그
ENABLE_QUICK_EDIT_MODE = 0x0040
ENABLE_EXTENDED_FLAGS = 0x0080
STD_INPUT_HANDLE = -10


def disable_quickedit_mode() -> int:
    """
    Windows Console QuickEdit Mode 비활성화
    
    QuickEdit Mode가 활성화되면 콘솔 창 클릭 시 스크립트가 일시정지됩니다.
    이 함수는 QuickEdit Mode를 비활성화하여 마우스 클릭으로 인한 멈춤을 방지합니다.
    
    Returns:
        이전 콘솔 모드 (복원용)
    """
    if platform.system() != "Windows":
        return 0
    
    try:
        kernel32 = ctypes.windll.kernel32
        
        # 표준 입력 핸들 얻기
        handle = kernel32.GetStdHandle(STD_INPUT_HANDLE)
        
        # 현재 콘솔 모드 읽기
        original_mode = ctypes.c_ulong()
        kernel32.GetConsoleMode(handle, ctypes.byref(original_mode))
        
        # QuickEdit Mode 비활성화
        new_mode = original_mode.value & ~ENABLE_QUICK_EDIT_MODE
        new_mode |= ENABLE_EXTENDED_FLAGS
        
        # 새 콘솔 모드 설정
        kernel32.SetConsoleMode(handle, new_mode)
        
        return original_mode.value
    
    except Exception as e:
        print(f"[경고] QuickEdit Mode 비활성화 실패: {e}")
        return 0


def restore_console_mode(original_mode: int) -> None:
    """
    콘솔 모드를 원래 설정으로 복원
    
    Args:
        original_mode: disable_quickedit_mode()에서 반환된 이전 모드
    """
    if platform.system() != "Windows" or original_mode == 0:
        return
    
    try:
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(STD_INPUT_HANDLE)
        kernel32.SetConsoleMode(handle, original_mode)
    
    except Exception as e:
        print(f"[경고] 콘솔 모드 복원 실패: {e}")

