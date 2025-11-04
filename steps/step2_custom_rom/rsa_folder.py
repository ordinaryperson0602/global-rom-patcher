"""RSA 폴더 관련 함수들"""
import os
import shutil
import traceback
from pathlib import Path
from typing import Tuple, Optional

from config.colors import Colors
from config.constants import UIConstants
from config.messages import TitleMessages
from core.logger import log_error
from utils.ui import show_popup
from utils.file_operations import remove_readonly_and_delete


# RSA 폴더 경로
RSA_BASE_DIR = r"C:\Programdata\RSA"
RSA_DOWNLOAD_DIR = r"C:\Programdata\RSA\Download"
RSA_ROMFILES_DIR = r"C:\Programdata\RSA\Download\Romfiles"


def check_and_prepare_rsa_folder() -> Tuple[bool, str]:
    """
    RSA 설치 확인 및 폴더 준비
    
    Returns:
        (성공 여부, Romfiles 폴더 경로)
    """
    print(f"\n{Colors.BOLD}{'='*60}{Colors.ENDC}")
    print(f"{Colors.BOLD}[STEP 0] RSA 설치 확인 및 폴더 준비{Colors.ENDC}")
    print(f"{Colors.BOLD}{'='*60}{Colors.ENDC}")
    
    # 1단계: RSA 기본 폴더 확인 (필수)
    print(f"\n{Colors.BOLD}[확인 1/3] RSA 설치 확인{Colors.ENDC}")
    print(f"  경로: {RSA_BASE_DIR}")
    
    if not os.path.exists(RSA_BASE_DIR):
        print(f"{Colors.FAIL}✗ RSA 폴더가 존재하지 않습니다.{Colors.ENDC}")
        
        # NG 팝업 표시
        show_popup(
            TitleMessages.ERROR,
            f"RSA 프로그램이 설치되지 않았습니다.\n\n"
            f"C:\\Programdata\\RSA 폴더가 없습니다.\n\n"
            f"RSA 다운로더를 먼저 설치한 후\n"
            f"다시 시도하세요.",
            exit_on_close=False,
            icon=UIConstants.ICON_ERROR
        )
        
        log_error("RSA 프로그램 미설치", context="STEP 0 - RSA 설치 확인")
        return False, ""
    
    print(f"{Colors.OKGREEN}✓ RSA가 설치되어 있습니다.{Colors.ENDC}")
    
    # 2단계: Download 폴더 확인 (자동 생성)
    print(f"\n{Colors.BOLD}[확인 2/3] Download 폴더 확인{Colors.ENDC}")
    print(f"  경로: {RSA_DOWNLOAD_DIR}")
    
    if not os.path.exists(RSA_DOWNLOAD_DIR):
        print(f"{Colors.WARNING}✗ Download 폴더가 없습니다. 생성합니다...{Colors.ENDC}")
        try:
            os.makedirs(RSA_DOWNLOAD_DIR, exist_ok=True)
            print(f"{Colors.OKGREEN}✓ Download 폴더를 생성했습니다.{Colors.ENDC}")
        except Exception as e:
            print(f"{Colors.FAIL}✗ Download 폴더 생성 실패: {e}{Colors.ENDC}")
            log_error(f"Download 폴더 생성 실패: {e}", exception=e, context="STEP 0")
            return False, ""
    else:
        print(f"{Colors.OKGREEN}✓ Download 폴더가 존재합니다.{Colors.ENDC}")
    
    # 3단계: Romfiles 폴더 확인 (자동 생성)
    print(f"\n{Colors.BOLD}[확인 3/3] Romfiles 폴더 확인{Colors.ENDC}")
    print(f"  경로: {RSA_ROMFILES_DIR}")
    
    if not os.path.exists(RSA_ROMFILES_DIR):
        print(f"{Colors.WARNING}✗ Romfiles 폴더가 없습니다. 생성합니다...{Colors.ENDC}")
        try:
            os.makedirs(RSA_ROMFILES_DIR, exist_ok=True)
            print(f"{Colors.OKGREEN}✓ Romfiles 폴더를 생성했습니다.{Colors.ENDC}")
        except Exception as e:
            print(f"{Colors.FAIL}✗ Romfiles 폴더 생성 실패: {e}{Colors.ENDC}")
            log_error(f"Romfiles 폴더 생성 실패: {e}", exception=e, context="STEP 0")
            return False, ""
    else:
        print(f"{Colors.OKGREEN}✓ Romfiles 폴더가 존재합니다.{Colors.ENDC}")
    
    print(f"\n{Colors.OKGREEN}✓ RSA 폴더 준비 완료!{Colors.ENDC}")
    return True, RSA_ROMFILES_DIR


def input_rsa_folder_name(device_model: str, rom_type: str) -> Optional[str]:
    """
    RSA용 폴더 이름 자동 추출 또는 사용자 입력
    
    Returns:
        입력받은 폴더 이름
    """
    print(f"\n{Colors.BOLD}{'='*60}{Colors.ENDC}")
    print(f"{Colors.BOLD}[STEP 5] RSA 폴더 이름 지정{Colors.ENDC}")
    print(f"{Colors.BOLD}{'='*60}{Colors.ENDC}")
    
    # 1단계: RSA RomFiles 폴더에서 .zip.tmp 파일 자동 검색
    rsa_romfiles_path = r"C:\ProgramData\RSA\Download\RomFiles"
    auto_detected_name = None
    
    print(f"\n{Colors.BOLD}[1/2] 자동 감지 시도{Colors.ENDC}")
    print(f"  경로: {rsa_romfiles_path}")
    
    if os.path.exists(rsa_romfiles_path):
        try:
            # .zip.tmp 파일 검색
            tmp_files = [f for f in os.listdir(rsa_romfiles_path) if f.endswith('.zip.tmp')]
            
            if tmp_files:
                # 가장 최근 파일 선택 (여러 개 있을 경우)
                latest_tmp = max(tmp_files, key=lambda f: os.path.getmtime(os.path.join(rsa_romfiles_path, f)))
                
                # .zip.tmp 제거하여 폴더 이름 추출
                auto_detected_name = latest_tmp.replace('.zip.tmp', '')
                
                print(f"{Colors.OKGREEN}✓ 최신 글로벌롬 파일 감지!{Colors.ENDC}")
                print(f"  파일: {latest_tmp}")
                print(f"  추출된 이름: {Colors.OKCYAN}{auto_detected_name}{Colors.ENDC}")
                
                # 자동 감지된 이름 사용 확인
                print(f"\n{Colors.BOLD}[안내]{Colors.ENDC}")
                if rom_type == 'china':
                    print(f"  내수롬을 위 글로벌롬 이름으로 위장합니다.")
                else:
                    print(f"  구버전 글로벌롬을 위 글로벌롬 이름으로 위장합니다.")
                
                while True:
                    response = input(f"\n{Colors.WARNING}자동 감지된 이름을 사용하시겠습니까? (y/n): {Colors.ENDC}").strip().lower()
                    if response == 'y':
                        return auto_detected_name
                    elif response == 'n':
                        print(f"{Colors.OKCYAN}수동 입력으로 전환합니다.{Colors.ENDC}")
                        break
                    else:
                        print(f"{Colors.FAIL}'y' 또는 'n'을 입력하세요.{Colors.ENDC}")
            else:
                print(f"{Colors.WARNING}⚠️  .zip.tmp 파일을 찾을 수 없습니다.{Colors.ENDC}")
                print(f"  RSA 프로그램에서 글로벌롬을 다운로드하세요.")
        
        except Exception as e:
            print(f"{Colors.WARNING}⚠️  자동 감지 실패: {e}{Colors.ENDC}")
    else:
        print(f"{Colors.WARNING}⚠️  RSA RomFiles 폴더가 존재하지 않습니다.{Colors.ENDC}")
    
    # 2단계: 수동 입력
    print(f"\n{Colors.BOLD}[2/2] 수동 입력{Colors.ENDC}")
    print(f"\n{Colors.BOLD}[안내]{Colors.ENDC}")
    print(f"  패치된 롬파일을 RSA 프로그램으로 플래싱하려면")
    print(f"  RSA가 인식할 수 있는 폴더 이름이 필요합니다.")
    
    if rom_type == 'china':
        print(f"\n{Colors.WARNING}⚠️  주의: 내수롬을 최신 글로벌롬 이름으로 위장해야 합니다!{Colors.ENDC}")
        print(f"  RSA 프로그램이 최신 글로벌롬만 인식하기 때문입니다.")
    else:
        print(f"\n{Colors.WARNING}⚠️  주의: 구버전 글로벌롬을 최신 글로벌롬 이름으로 위장해야 합니다!{Colors.ENDC}")
        print(f"  RSA 프로그램이 최신 글로벌롬만 인식하기 때문입니다.")
    
    print(f"\n{Colors.BOLD}[폴더 이름 형식]{Colors.ENDC}")
    print(f"  {Colors.OKCYAN}예시: TB520FU_ROW_OPEN_USER_Q00002.0_W_ZUI_17.5.10.035_ST_250923{Colors.ENDC}")
    print(f"\n{Colors.BOLD}[확인 방법]{Colors.ENDC}")
    print(f"  1. RSA 프로그램을 실행하세요")
    print(f"  2. 최신 글로벌롬 이름을 확인하세요 (RSA에서 표시되는 이름)")
    print(f"  3. 아래에 정확히 입력하세요")
    
    while True:
        print(f"\n{Colors.WARNING}RSA용 폴더 이름을 입력하세요:{Colors.ENDC}")
        folder_name = input(f"{Colors.WARNING}> {Colors.ENDC}").strip()
        
        if not folder_name:
            print(f"{Colors.FAIL}폴더 이름이 비어있습니다. 다시 입력하세요.{Colors.ENDC}")
            continue
        
        # 기본 검증
        if device_model not in folder_name:
            print(f"\n{Colors.WARNING}⚠️  경고: 입력한 이름에 기기 모델({device_model})이 없습니다.{Colors.ENDC}")
            response = input(f"{Colors.WARNING}그래도 사용하시겠습니까? (y/n): {Colors.ENDC}").strip().lower()
            if response != 'y':
                continue
        
        # 확인
        print(f"\n{Colors.BOLD}입력한 폴더 이름:{Colors.ENDC}")
        print(f"  {Colors.OKCYAN}{folder_name}{Colors.ENDC}")
        
        response = input(f"\n{Colors.WARNING}이 이름으로 확정하시겠습니까? (y/n): {Colors.ENDC}").strip().lower()
        if response == 'y':
            return folder_name
        else:
            print(f"{Colors.OKCYAN}다시 입력하세요.{Colors.ENDC}")


def move_to_rsa_folder(patched_rom_path: str, rsa_dir: str, rsa_folder_name: str) -> bool:
    """
    패치된 롬파일을 RSA 폴더로 이동 (잘라내기)
    
    Args:
        patched_rom_path: 패치된 롬파일 경로 (_PATCH 폴더)
        rsa_dir: RSA Romfiles 폴더 경로
        rsa_folder_name: RSA용 폴더 이름
    """
    print(f"\n{Colors.BOLD}[이동] RSA 폴더로 이동 중...{Colors.ENDC}")
    
    # 1단계: _PATCH 폴더를 RSA 폴더 이름으로 변경
    patch_parent = os.path.dirname(patched_rom_path)
    renamed_path = os.path.join(patch_parent, rsa_folder_name)
    destination_path = os.path.join(rsa_dir, rsa_folder_name)
    
    print(f"  [1/2] 폴더 이름 변경")
    print(f"    현재: {os.path.basename(patched_rom_path)}")
    print(f"    변경: {rsa_folder_name}")
    
    # 이름 변경된 폴더가 이미 존재하는지 확인
    if os.path.exists(renamed_path) and renamed_path != patched_rom_path:
        print(f"\n{Colors.WARNING}⚠️  변경할 이름의 폴더가 이미 존재합니다!{Colors.ENDC}")
        print(f"  {renamed_path}")
        while True:
            response = input(f"\n{Colors.WARNING}기존 폴더를 삭제하고 계속하시겠습니까? (y/n): {Colors.ENDC}").strip().lower()
            if response == 'y':
                try:
                    # 읽기 전용 파일도 강제로 삭제
                    remove_readonly_and_delete(Path(renamed_path))
                    print(f"{Colors.OKCYAN}기존 폴더를 삭제했습니다.{Colors.ENDC}")
                except Exception as e:
                    print(f"{Colors.FAIL}삭제 실패: {e}{Colors.ENDC}")
                    log_error(f"이름 변경 전 폴더 강제 삭제 실패: {e}", exception=e, context="move_to_rsa_folder")
                    return False
                break
            elif response == 'n':
                print(f"{Colors.OKCYAN}작업을 취소합니다.{Colors.ENDC}")
                return False
            else:
                print(f"{Colors.FAIL}'y' 또는 'n'을 입력하세요.{Colors.ENDC}")
    
    try:
        # 폴더 이름 변경
        if patched_rom_path != renamed_path:
            os.rename(patched_rom_path, renamed_path)
            print(f"{Colors.OKGREEN}  ✓ 이름 변경 완료{Colors.ENDC}")
        else:
            print(f"{Colors.OKCYAN}  이미 올바른 이름입니다.{Colors.ENDC}")
    except Exception as e:
        print(f"\n{Colors.FAIL}✗ 이름 변경 실패: {e}{Colors.ENDC}")
        log_error(f"폴더 이름 변경 실패: {e}", exception=e, context="STEP 5 - 이름 변경")
        return False
    
    # 2단계: RSA 폴더로 이동
    print(f"\n  [2/2] RSA 폴더로 이동 (잘라내기)")
    print(f"    대상: {destination_path}")
    
    # RSA 대상 폴더 존재 확인
    if os.path.exists(destination_path):
        print(f"\n{Colors.WARNING}⚠️  RSA 폴더에 동일한 이름의 폴더가 이미 존재합니다!{Colors.ENDC}")
        print(f"  {destination_path}")
        
        while True:
            response = input(f"\n{Colors.WARNING}덮어쓰시겠습니까? (y/n): {Colors.ENDC}").strip().lower()
            if response == 'y':
                print(f"{Colors.WARNING}기존 폴더를 강제 삭제합니다...{Colors.ENDC}")
                try:
                    # 읽기 전용 파일도 강제로 삭제
                    remove_readonly_and_delete(Path(destination_path))
                    print(f"{Colors.OKGREEN}✓ 삭제 완료{Colors.ENDC}")
                except Exception as e:
                    print(f"{Colors.FAIL}삭제 실패: {e}{Colors.ENDC}")
                    log_error(f"RSA 대상 폴더 강제 삭제 실패: {e}", exception=e, context="move_to_rsa_folder")
                    # 이름 변경한 폴더를 원래대로 되돌림
                    try:
                        os.rename(renamed_path, patched_rom_path)
                    except:
                        pass
                    return False
                break
            elif response == 'n':
                print(f"{Colors.OKCYAN}작업을 취소합니다.{Colors.ENDC}")
                # 이름 변경한 폴더를 원래대로 되돌림
                try:
                    os.rename(renamed_path, patched_rom_path)
                    print(f"{Colors.OKCYAN}폴더 이름을 원래대로 되돌렸습니다.{Colors.ENDC}")
                except Exception as e:
                    print(f"{Colors.WARNING}폴더 이름 복구 실패: {e}{Colors.ENDC}")
                return False
            else:
                print(f"{Colors.FAIL}'y' 또는 'n'을 입력하세요.{Colors.ENDC}")
    
    # 이동 (잘라내기)
    try:
        shutil.move(renamed_path, destination_path)
        
        print(f"\n{Colors.OKGREEN}✓ 이동 완료!{Colors.ENDC}")
        print(f"  최종 위치: {destination_path}")
        print(f"  {Colors.OKCYAN}원본 _PATCH 폴더는 삭제되었습니다.{Colors.ENDC}")
        return True
    
    except Exception as e:
        print(f"\n{Colors.FAIL}✗ 이동 실패: {e}{Colors.ENDC}")
        log_error(f"RSA 폴더 이동 실패: {e}", exception=e, context="STEP 5 - RSA 이동")
        # 이름 변경한 폴더를 원래대로 되돌림
        try:
            if os.path.exists(renamed_path):
                os.rename(renamed_path, patched_rom_path)
                print(f"{Colors.OKCYAN}폴더 이름을 원래대로 되돌렸습니다.{Colors.ENDC}")
        except Exception as rollback_e:
            print(f"{Colors.WARNING}폴더 이름 복구 실패: {rollback_e}{Colors.ENDC}")
        return False


def show_rsa_flash_guide(rsa_folder_path: str) -> None:
    """
    RSA 프로그램으로 플래싱하는 방법 안내
    """
    print(f"\n{Colors.OKGREEN}{'='*60}{Colors.ENDC}")
    print(f"{Colors.OKGREEN}✓ 모든 작업이 완료되었습니다!{Colors.ENDC}")
    print(f"{Colors.OKGREEN}{'='*60}{Colors.ENDC}")
    
    print(f"\n{Colors.BOLD}[다음 단계] RSA 프로그램으로 플래싱{Colors.ENDC}")
    print(f"\n{Colors.OKCYAN}1. RSA 다운로더 프로그램을 실행하세요.{Colors.ENDC}")
    print(f"\n{Colors.OKCYAN}2. RSA에서 다음 롬파일이 표시되는지 확인하세요:{Colors.ENDC}")
    print(f"   {Colors.BOLD}{os.path.basename(rsa_folder_path)}{Colors.ENDC}")
    print(f"\n{Colors.OKCYAN}3. 해당 롬파일을 선택하고 플래싱을 진행하세요.{Colors.ENDC}")
    
    input(f"\n{Colors.OKGREEN}Enter 키를 눌러 종료...{Colors.ENDC}")

