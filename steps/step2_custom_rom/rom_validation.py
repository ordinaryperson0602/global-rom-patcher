"""ROM 검증 관련 함수들"""
import os
from typing import Tuple

from config.colors import Colors
from config.constants import UIConstants
from config.messages import TitleMessages
from core.logger import log_error
from utils.ui import show_popup


def validate_rom_structure(rom_path: str, rom_type: str) -> Tuple[bool, str]:
    """
    롬파일 필수 구조 검증
    
    Returns:
        (검증 성공 여부, 에러 메시지)
    """
    print(f"\n{Colors.BOLD}[검증] 롬파일 구조 확인 중...{Colors.ENDC}")
    
    # 필수 파일 정의
    if rom_type == 'global':
        required_files = [
            'image/vbmeta.img',
            'image/vbmeta_system.img',
            'image/vendor_boot.img',
            'image/boot.img',
        ]
    else:  # china
        required_files = [
            'image/vbmeta_system.img',
            'image/boot.img',
        ]
    
    # 필수 파일 확인
    missing_files = []
    
    for file_path in required_files:
        full_path = os.path.join(rom_path, file_path)
        if os.path.exists(full_path):
            file_size_mb = os.path.getsize(full_path) / (1024*1024)
            print(f"  ✓ {file_path} ({file_size_mb:.1f} MB)")
        else:
            print(f"  ✗ {file_path} (누락)")
            missing_files.append(file_path)
    
    if missing_files:
        error_msg = f"필수 파일이 누락되었습니다:\n" + "\n".join(f"  - {f}" for f in missing_files)
        return False, error_msg
    
    print(f"{Colors.OKGREEN}✓ 모든 필수 파일이 존재합니다.{Colors.ENDC}")
    return True, ""


def verify_model_compatibility(device_model: str, rom_path: str) -> bool:
    """
    기기 모델과 롬파일 모델 호환성 검증
    
    Args:
        device_model: 기기 모델 (예: TB520FU)
        rom_path: 롬파일 경로
    
    Returns:
        True: 호환 가능
        False: 호환 불가 (NG 처리)
    """
    print(f"\n{Colors.BOLD}[검증] 모델 호환성 확인{Colors.ENDC}")
    
    folder_name = os.path.basename(rom_path)
    print(f"  기기 모델: {Colors.BOLD}{device_model}{Colors.ENDC}")
    print(f"  롬 폴더명: {folder_name}")
    
    # 1차 매칭: 전체 모델명 (예: TB520FU)
    if device_model in folder_name:
        print(f"{Colors.OKGREEN}✓ 모델이 일치합니다. (전체 매칭){Colors.ENDC}")
        return True
    
    # 2차 매칭: 부분 모델명 (예: TB520FU → TB520)
    # 내수롬은 보통 TB520만 사용 (FU 없음)
    base_model = device_model.rstrip('FU')  # TB520FU → TB520
    
    if base_model != device_model and base_model in folder_name:
        print(f"{Colors.OKGREEN}✓ 모델이 일치합니다. (부분 매칭: {base_model}){Colors.ENDC}")
        print(f"{Colors.OKCYAN}  [참고] 내수롬은 보통 {base_model} 형식을 사용합니다.{Colors.ENDC}")
        return True
    
    # 불일치 → NG 처리 (에러 팝업)
    print(f"\n{Colors.FAIL}{'='*60}{Colors.ENDC}")
    print(f"{Colors.FAIL}❌ 오류: 모델이 일치하지 않습니다!{Colors.ENDC}")
    print(f"{Colors.FAIL}{'='*60}{Colors.ENDC}")
    print(f"  기기 모델: {Colors.BOLD}{device_model}{Colors.ENDC}")
    print(f"  롬 폴더:   {Colors.BOLD}{folder_name}{Colors.ENDC}")
    
    # NG 팝업 표시
    show_popup(
        TitleMessages.ERROR,
        f"모델이 일치하지 않습니다!\n\n"
        f"기기 모델: {device_model}\n"
        f"롬 폴더: {folder_name}\n\n"
        f"잘못된 모델의 롬을 플래싱하면\n"
        f"기기가 벽돌화될 수 있습니다.\n\n"
        f"올바른 모델의 롬파일을 선택하세요.",
        exit_on_close=False,
        icon=UIConstants.ICON_ERROR
    )
    
    log_error(f"모델 불일치: 기기({device_model}) vs 롬({folder_name})", context="STEP 2-Custom - 모델 검증")
    
    return False


def show_safety_confirmation(rom_type: str, rom_path: str, device_model: str) -> bool:
    """
    최종 안전 확인 프롬프트
    """
    print(f"\n{Colors.BOLD}{'='*60}{Colors.ENDC}")
    print(f"{Colors.BOLD}        최종 확인{Colors.ENDC}")
    print(f"{Colors.BOLD}{'='*60}{Colors.ENDC}")
    
    # 롬 타입에 따른 위험도 표시
    if rom_type == 'china':
        risk_level = f"{Colors.FAIL}⚠️  HIGH RISK ⚠️{Colors.ENDC}"
        warning = "내수롬 패치는 검증이 덜 된 기능입니다!"
    else:
        risk_level = f"{Colors.WARNING}⚠️  MEDIUM RISK{Colors.ENDC}"
        warning = "사용자 지정 롬파일은 책임이 사용자에게 있습니다."
    
    folder_name = os.path.basename(rom_path)
    
    print(f"\n{Colors.BOLD}[롬 정보]{Colors.ENDC}")
    print(f"  타입:     {rom_type.upper()} ({'글로벌' if rom_type == 'global' else '내수'})")
    print(f"  폴더:     {folder_name}")
    
    print(f"\n{Colors.BOLD}[기기 정보]{Colors.ENDC}")
    print(f"  모델:     {device_model}")
    
    print(f"\n{Colors.BOLD}[위험도]{Colors.ENDC}")
    print(f"  {risk_level}")
    print(f"  {Colors.WARNING}{warning}{Colors.ENDC}")
    
    print(f"\n{Colors.BOLD}[패치 대상]{Colors.ENDC}")
    if rom_type == 'global':
        print(f"  ✓ vbmeta")
        print(f"  ✓ vbmeta_system")
        print(f"  ✓ vendor_boot")
        print(f"  ✓ boot (루팅 선택 시)")
    else:
        print(f"  ✗ vbmeta (건너뛰기)")
        print(f"  ✓ vbmeta_system")
        print(f"  ✗ vendor_boot (건너뛰기)")
        print(f"  ✓ boot (루팅 선택 시)")
    
    print(f"\n{Colors.BOLD}{'='*60}{Colors.ENDC}")
    
    # 최종 확인
    while True:
        response = input(f"\n{Colors.WARNING}위 내용을 확인했으며 패치를 진행하시겠습니까? (yes/no): {Colors.ENDC}").strip().lower()
        if response == 'yes':
            print(f"\n{Colors.OKGREEN}✓ 패치를 시작합니다...{Colors.ENDC}")
            return True
        elif response == 'no':
            print(f"\n{Colors.OKCYAN}작업을 취소합니다.{Colors.ENDC}")
            return False
        else:
            print(f"{Colors.FAIL}'yes' 또는 'no'를 입력하세요.{Colors.ENDC}")

