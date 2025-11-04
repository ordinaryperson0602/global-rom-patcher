"""실행 컨텍스트 관리"""
from pathlib import Path
from typing import Optional


class DeviceContext:
    """기기 추출 관련 상태 관리"""
    def __init__(self) -> None:
        """DeviceContext 초기화"""
        self.selected_loader_file: Optional[str] = None
        self.output_folder_path: Optional[Path] = None
    
    def set_loader(self, loader_path: str) -> None:
        """로더 파일 경로 설정"""
        self.selected_loader_file = loader_path
    
    def set_output_folder(self, output_path: Path) -> None:
        """출력 폴더 경로 설정"""
        self.output_folder_path = output_path
    
    def get_loader(self) -> Optional[str]:
        """로더 파일 경로 반환"""
        return self.selected_loader_file
    
    def get_output_folder(self) -> Optional[Path]:
        """출력 폴더 경로 반환"""
        return self.output_folder_path


class CopyProgressTracker:
    """파일 복사 진행률 추적"""
    def __init__(self) -> None:
        """CopyProgressTracker 초기화"""
        self.total_file_count: int = 0
        self.copied_file_count: int = 0
    
    def set_total(self, count: int) -> None:
        """총 파일 개수 설정"""
        self.total_file_count = count
        self.copied_file_count = 0
    
    def increment(self) -> None:
        """복사된 파일 개수 증가"""
        self.copied_file_count += 1
    
    def reset(self) -> None:
        """카운터 리셋"""
        self.total_file_count = 0
        self.copied_file_count = 0
    
    def get_progress_str(self) -> str:
        """진행률 문자열 반환"""
        if self.total_file_count > 0:
            percentage = (self.copied_file_count / self.total_file_count) * 100
            return f"{self.copied_file_count}/{self.total_file_count} ({percentage:.1f}%)"
        return "0/0 (0.0%)"

