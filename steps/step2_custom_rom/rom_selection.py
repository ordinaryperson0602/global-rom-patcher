"""ROM 선택 관련 함수들"""
import os
import traceback
import tkinter as tk
from tkinter import filedialog
from typing import Optional, Tuple

from config.colors import Colors
from core.logger import log_error


def select_rom_folder() -> Optional[str]:
    """
    GUI 폴더 선택 다이얼로그
    
    Returns:
        선택한 롬파일 폴더 경로 (취소 시 None)
    """
    print(f"\n{Colors.BOLD}{'='*60}{Colors.ENDC}")
    print(f"{Colors.BOLD}[STEP 2-Custom] 사용자 지정 롬파일 선택{Colors.ENDC}")
    print(f"{Colors.BOLD}{'='*60}{Colors.ENDC}")
    
    print(f"\n{Colors.WARNING}파일 탐색기 창에서 롬파일 폴더를 선택하세요...{Colors.ENDC}")
    print(f"{Colors.OKCYAN}  (예: TB520FU_ROW_OPEN_USER_... 또는 TB520FU_CN_...){Colors.ENDC}")
    
    try:
        root = tk.Tk()
        root.withdraw()  # 메인 창 숨김
        root.attributes('-topmost', True)  # 최상단 표시
        
        folder_path = filedialog.askdirectory(
            title="롬파일 폴더를 선택하세요",
            initialdir="C:\\"
        )
        
        root.destroy()
        
        if not folder_path:
            print(f"\n{Colors.WARNING}[알림] 폴더 선택이 취소되었습니다.{Colors.ENDC}")
            return None
        
        print(f"\n{Colors.OKGREEN}✓ 선택한 경로:{Colors.ENDC}")
        print(f"  {folder_path}")
        
        # 폴더 확인
        print(f"\n{Colors.BOLD}{'='*60}{Colors.ENDC}")
        print(f"{Colors.BOLD}선택한 폴더 확인{Colors.ENDC}")
        print(f"{Colors.BOLD}{'='*60}{Colors.ENDC}")
        
        folder_name = os.path.basename(folder_path)
        print(f"\n  폴더명: {Colors.BOLD}{folder_name}{Colors.ENDC}")
        print(f"  경로: {folder_path}")
        
        while True:
            confirm = input(f"\n{Colors.WARNING}이 폴더가 맞습니까? (y/n): {Colors.ENDC}").strip().lower()
            if confirm == 'y':
                print(f"\n{Colors.OKGREEN}✓ 폴더 선택 확인됨{Colors.ENDC}")
                return folder_path
            elif confirm == 'n':
                print(f"\n{Colors.WARNING}[알림] 폴더 선택이 취소되었습니다.{Colors.ENDC}")
                return None
            else:
                print(f"{Colors.FAIL}'y' 또는 'n'을 입력하세요.{Colors.ENDC}")
    
    except Exception as e:
        print(f"\n{Colors.FAIL}[오류] 폴더 선택 중 오류 발생: {e}{Colors.ENDC}")
        log_error(f"폴더 선택 실패: {e}", exception=e, context="STEP 2-Custom - 롬파일 선택")
        return None


def find_actual_rom_path(selected_path: str) -> Tuple[Optional[str], bool]:
    """
    실제 image 폴더가 있는 경로를 찾음 (최대 3단계 중첩 폴더 처리)
    
    Args:
        selected_path: 사용자가 선택한 롬파일 폴더 경로
    
    Returns:
        (actual_path, is_nested)
        - actual_path: image 폴더가 있는 실제 경로
        - is_nested: 중첩 구조 여부 (True면 하위 폴더 사용)
    """
    print(f"\n{Colors.BOLD}[폴더 구조 분석]{Colors.ENDC}")
    
    # 최대 3단계까지 중첩 검사
    max_depth = 3
    current_path = selected_path
    
    for depth in range(max_depth):
        image_path = os.path.join(current_path, "image")
        
        if os.path.exists(image_path) and os.path.isdir(image_path):
            if depth == 0:
                print(f"{Colors.OKGREEN}✓ 정상 구조: image 폴더 직접 발견{Colors.ENDC}")
                print(f"  {current_path}/image")
                return current_path, False
            else:
                print(f"{Colors.OKGREEN}✓ 중첩 구조 감지 ({depth}단계): image 폴더를 하위에서 발견{Colors.ENDC}")
                print(f"  {current_path}/image")
                print(f"{Colors.OKCYAN}  패치 시 내부 폴더만 사용됩니다.{Colors.ENDC}")
                return current_path, True
        else:
            # image 폴더가 없으면 하위 폴더 확인
            if depth == 0:
                print(f"{Colors.WARNING}  image 폴더를 직접 찾을 수 없습니다. 하위 폴더를 확인합니다...{Colors.ENDC}")
            
            try:
                items = os.listdir(current_path)
                subdirs = [item for item in items if os.path.isdir(os.path.join(current_path, item))]
                
                if len(subdirs) == 1:
                    nested_folder = subdirs[0]
                    current_path = os.path.join(current_path, nested_folder)
                    print(f"{Colors.OKCYAN}  → {depth + 1}단계 하위 폴더: {nested_folder}{Colors.ENDC}")
                elif len(subdirs) == 0:
                    print(f"{Colors.FAIL}✗ 하위 폴더가 없습니다.{Colors.ENDC}")
                    return None, False
                else:
                    print(f"{Colors.FAIL}✗ 하위 폴더가 {len(subdirs)}개 있습니다. 구조를 확인할 수 없습니다.{Colors.ENDC}")
                    return None, False
            
            except Exception as e:
                print(f"{Colors.FAIL}✗ 폴더 구조 분석 실패: {e}{Colors.ENDC}")
                log_error(f"폴더 구조 분석 실패: {e}", exception=e, context="find_actual_rom_path")
                return None, False
    
    # 최대 깊이까지 검사했는데도 image 폴더를 못 찾음
    print(f"{Colors.FAIL}✗ 최대 {max_depth}단계까지 검사했으나 image 폴더를 찾을 수 없습니다.{Colors.ENDC}")
    return None, False

