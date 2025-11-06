"""파일 작업 유틸리티"""
import os
import shutil
import stat
import sys
from pathlib import Path
from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from core.context import CopyProgressTracker

from src.config import Colors


def _get_long_path(path: str) -> str:
    """Windows 긴 경로 지원을 위한 경로 변환"""
    if sys.platform == 'win32':
        # 절대 경로로 변환
        abs_path = os.path.abspath(path)
        # 이미 \\?\ 접두사가 있으면 그대로 반환
        if abs_path.startswith('\\\\?\\'):
            return abs_path
        # UNC 경로가 아니면 \\?\ 접두사 추가
        if abs_path.startswith('\\\\'):
            return '\\\\?\\UNC\\' + abs_path[2:]
        else:
            return '\\\\?\\' + abs_path
    return path


def copy_with_progress(src: str, dst: str, tracker: 'CopyProgressTracker') -> None:
    """
    진행률 표시하며 파일 복사 (긴 경로 지원)
    
    Args:
        src: 원본 파일 경로
        dst: 대상 파일 경로
        tracker: CopyProgressTracker 인스턴스
    """
    try:
        # 긴 경로 지원
        long_src = _get_long_path(src)
        long_dst = _get_long_path(dst)
        
        # 대상 디렉토리 생성
        dst_dir = os.path.dirname(long_dst)
        if not os.path.exists(dst_dir):
            os.makedirs(dst_dir, exist_ok=True)
        
        shutil.copy2(long_src, long_dst)
        tracker.increment()
        
        if tracker.total_file_count > 0:
            percent = (tracker.copied_file_count / tracker.total_file_count) * 100
            bar_length = 40
            filled = int(bar_length * tracker.copied_file_count / tracker.total_file_count)
            bar = '█' * filled + '-' * (bar_length - filled)
            
            sys.stdout.write(
                f"\r  복사 중: [{Colors.OKGREEN}{bar}{Colors.ENDC}] "
                f"{tracker.copied_file_count}/{tracker.total_file_count} "
                f"{Colors.OKBLUE}({percent:.1f}%){Colors.ENDC}"
            )
            sys.stdout.flush()
    except Exception as e:
        from core.logger import log_error
        error_msg = f"파일 복사 실패: {src}"
        print(f"\n{error_msg} -> {e}", flush=True)
        log_error(error_msg, exception=e, context="파일 복사")


def remove_readonly_and_delete(path: Path) -> None:
    """읽기 전용 파일을 삭제 가능하게 만들고 삭제"""
    def remove_readonly(func: Callable, file_path: str, excinfo: Any) -> None:
        """읽기 전용 속성 제거 후 재시도"""
        os.chmod(file_path, stat.S_IWRITE)
        func(file_path)
    
    if path.is_file():
        os.chmod(path, stat.S_IWRITE)
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path, onerror=remove_readonly)


def safe_delete_tree(directory: Path) -> bool:
    """안전하게 디렉토리 트리 삭제"""
    try:
        if directory.exists():
            remove_readonly_and_delete(directory)
        return True
    except Exception as e:
        print(f"[경고] 디렉토리 삭제 실패: {directory} - {e}")
        return False


def get_total_files(src_dir: str) -> int:
    """폴더 내 총 파일 개수 계산 (긴 경로 지원)"""
    count = 0
    # Windows 긴 경로 지원
    long_path = _get_long_path(src_dir)
    for root, _, files in os.walk(long_path):
        count += len(files)
    return count

