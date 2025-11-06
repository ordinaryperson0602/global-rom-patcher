"""ROM 타입 감지 관련 함수들"""
import os
import re
import sys
from typing import Tuple, Dict, Any

from src.config import Colors
from src.config import AVBTOOL_PY
from utils.command import run_command


# Helper Functions (리팩토링)
def _analyze_vbmeta_prop(vbmeta_path: str, target_model: str = None) -> Tuple[str, Dict[str, Any]]:
    """1단계: vbmeta.img Prop 분석"""
    if not os.path.exists(vbmeta_path):
        raise Exception(f"vbmeta.img 파일을 찾을 수 없습니다: {vbmeta_path}")
    
    print(f"\n{Colors.BOLD}[1단계] vbmeta.img Prop 분석{Colors.ENDC}")
    
    try:
        # avbtool로 Prop 추출
        from config.paths import PYTHON_EXE
        cmd = [PYTHON_EXE, AVBTOOL_PY, 'info_image', '--image', vbmeta_path]
        success, output, _ = run_command(cmd, "vbmeta.img Prop 추출")
        
        if not success or not output:
            raise Exception("vbmeta.img Prop 추출 실패")
        
        # Prop 문자열에서 PRC/ROW 카운트
        prop_text = output.upper()
        prc_count = prop_text.count('PRC')
        row_count = prop_text.count('ROW')
        
        print(f"  - PRC 문자열: {prc_count}개")
        print(f"  - ROW 문자열: {row_count}개")
        
        # fingerprint에서 모델 번호 추출 (2차 검증용)
        rom_info = {'model': 'unknown'}
        extracted_models = set()
        fingerprint_regex = re.compile(
            r"'[^/]+/([^/]+)/[^:]+:[^/]+/((.*?)_(PRC|ROW)):user/release-keys'"
        )
        
        for line in output.splitlines():
            line_stripped = line.strip()
            if line_stripped.startswith("Prop:") and "fingerprint" in line_stripped:
                match = fingerprint_regex.search(line_stripped)
                if match:
                    model = match.group(1)
                    extracted_models.add(model)
        
        # 2차 검증: vbmeta Prop 모델 번호와 기기 모델 번호 비교
        if target_model and extracted_models:
            prop_model = list(extracted_models)[0]
            if prop_model != target_model:
                raise Exception(
                    f"vbmeta Prop의 모델 번호가 기기 모델과 일치하지 않습니다.\n"
                    f"기기 모델: {target_model}\n"
                    f"롬 모델: {prop_model}\n"
                    f"올바른 모델의 롬파일을 선택하세요."
                )
            print(f"  - [2차 검증] vbmeta Prop 모델 번호: {prop_model} ✓")
            rom_info['model'] = prop_model
        
        # Prop 판정
        prop_is_prc = (prc_count > 0 and row_count == 0)
        prop_is_row = (row_count > 0 and prc_count == 0)
        
        if not prop_is_prc and not prop_is_row:
            if prc_count > 0 and row_count > 0:
                raise Exception(f"vbmeta.img Prop에 PRC와 ROW가 혼합되어 있습니다 (PRC:{prc_count}, ROW:{row_count})")
            else:
                raise Exception("vbmeta.img Prop에서 지역 코드를 찾을 수 없습니다")
        
        prop_type = 'PRC' if prop_is_prc else 'ROW'
        print(f"  → Prop 판정: {Colors.WARNING if prop_is_prc else Colors.OKGREEN}{prop_type}{Colors.ENDC}")
        
        return prop_type, rom_info
    
    except Exception as e:
        error_msg = f"vbmeta.img Prop 분석 실패: {e}"
        print(f"\n{Colors.FAIL}[오류] {error_msg}{Colors.ENDC}")
        raise Exception(error_msg)


def _analyze_vendor_boot_hex(vendor_boot_path: str) -> Tuple[bool, str]:
    """2단계: vendor_boot.img Hex 코드 분석"""
    print(f"\n{Colors.BOLD}[2단계] vendor_boot.img Hex 코드 분석{Colors.ENDC}")
    
    if not os.path.exists(vendor_boot_path):
        print(f"  - vendor_boot.img: ✗ 없음")
        print(f"  → vendor_boot 없음 (내수롬 가능성)")
        return False, None
    
    print(f"  - vendor_boot.img: ✓ 존재")
    
    try:
        # vendor_boot 바이너리 읽기
        with open(vendor_boot_path, 'rb') as f:
            vendor_data = f.read()
        
        # Hex 패턴 검색
        from config.constants import HEX_PRC, HEX_IPRC, HEX_ROW, HEX_IROW
        from utils.region_check import check_region_patterns
        
        found_prc, found_iprc, found_row, found_irow = check_region_patterns(vendor_data)
        
        print(f"  - HEX_PRC:  {'✓ 발견' if found_prc else '✗ 없음'}")
        print(f"  - HEX_IPRC: {'✓ 발견' if found_iprc else '✗ 없음'}")
        print(f"  - HEX_ROW:  {'✓ 발견' if found_row else '✗ 없음'}")
        print(f"  - HEX_IROW: {'✓ 발견' if found_irow else '✗ 없음'}")
        
        # Hex 판정
        has_prc_type = found_prc or found_iprc
        has_row_type = found_row or found_irow
        
        # 혼합 체크
        if has_prc_type and has_row_type:
            raise Exception("vendor_boot.img에 PRC/IPRC와 ROW/IROW가 혼합되어 있습니다")
        
        if found_prc and found_iprc:
            raise Exception("vendor_boot.img에 HEX_PRC와 HEX_IPRC가 혼합되어 있습니다 (롬파일 이상)")
        
        if found_row and found_irow:
            raise Exception("vendor_boot.img에 HEX_ROW와 HEX_IROW가 혼합되어 있습니다 (롬파일 이상)")
        
        # 판정
        if has_prc_type:
            hex_type = 'PRC'
            print(f"  → Hex 판정: {Colors.WARNING}{hex_type}{Colors.ENDC}")
        elif has_row_type:
            hex_type = 'ROW'
            print(f"  → Hex 판정: {Colors.OKGREEN}{hex_type}{Colors.ENDC}")
        else:
            raise Exception("vendor_boot.img에서 지역 코드(HEX)를 찾을 수 없습니다")
        
        return True, hex_type
    
    except Exception as e:
        error_msg = f"vendor_boot.img Hex 분석 실패: {e}"
        print(f"\n{Colors.FAIL}[오류] {error_msg}{Colors.ENDC}")
        raise Exception(error_msg)


def _make_final_decision(prop_type: str, has_vendor_boot: bool, hex_type: str) -> str:
    """3단계: 최종 판정"""
    print(f"\n{Colors.BOLD}[3단계] 최종 판정{Colors.ENDC}")
    
    # 내수롬 조건
    if prop_type == 'PRC':
        if not has_vendor_boot:
            # vendor_boot 없음 → 내수롬 가능
            print(f"  - Prop: PRC")
            print(f"  - vendor_boot: 없음")
            return 'china'
        elif hex_type == 'PRC':
            # Prop PRC + Hex PRC → 내수롬 확정
            print(f"  - Prop: PRC")
            print(f"  - Hex: PRC")
            return 'china'
        else:
            # Prop PRC + Hex ROW → 이상!
            raise Exception(f"Prop은 PRC인데 vendor_boot Hex는 {hex_type}입니다 (롬파일 이상)")
    
    # 글로벌롬 조건
    elif prop_type == 'ROW':
        if not has_vendor_boot:
            # vendor_boot 없음 → 이상 (글로벌롬인데 vendor_boot 없음)
            raise Exception("Prop은 ROW인데 vendor_boot.img가 없습니다 (롬파일 이상)")
        elif hex_type == 'ROW':
            # Prop ROW + Hex ROW → 글로벌롬 확정
            print(f"  - Prop: ROW")
            print(f"  - Hex: ROW")
            return 'global'
        else:
            # Prop ROW + Hex PRC → 이상!
            raise Exception(f"Prop은 ROW인데 vendor_boot Hex는 {hex_type}입니다 (롬파일 이상)")
    
    else:
        raise Exception("알 수 없는 Prop 타입입니다")


def detect_rom_type(rom_path: str, target_model: str = None) -> Tuple[str, Dict[str, Any]]:
    """
    롬 타입 자동 감지 (글로벌/내수) - 리팩토링 버전
    
    정확한 감지 로직:
    1. vbmeta_system.img Prop 분석 (ROW/PRC 문자열)
    2. vendor_boot.img Hex 코드 분석 (HEX_ROW/HEX_PRC 패턴)
    3. 두 결과를 종합하여 판정
    4. (선택) vbmeta Prop 모델 번호와 기기 모델 번호 비교 (2차 검증)
    
    Args:
        rom_path: 롬파일 경로
        target_model: 기기 모델 번호 (None이면 2차 검증 생략)
    
    Returns:
        (rom_type, rom_info)
        rom_type: 'global' 또는 'china'
    
    Raises:
        Exception: 롬파일 이상 (혼합, 누락 등)
    """
    print(f"\n{Colors.BOLD}[분석] 롬 타입 자동 감지 중...{Colors.ENDC}")
    
    rom_info = {
        'type': 'unknown',
        'model': 'unknown',
        'version': 'unknown',
        'region_code': 'unknown',
    }
    
    folder_name = os.path.basename(rom_path)
    print(f"  - 폴더명: {folder_name}")
    
    # 1단계: vbmeta.img Prop 분석
    vbmeta_path = os.path.join(rom_path, 'image', 'vbmeta.img')
    prop_type, prop_info = _analyze_vbmeta_prop(vbmeta_path, target_model)
    rom_info.update(prop_info)
    
    # 2단계: vendor_boot.img Hex 코드 분석
    vendor_boot_path = os.path.join(rom_path, 'image', 'vendor_boot.img')
    has_vendor_boot, hex_type = _analyze_vendor_boot_hex(vendor_boot_path)
    
    # 3단계: 최종 판정
    rom_type = _make_final_decision(prop_type, has_vendor_boot, hex_type)
    
    rom_info['type'] = rom_type
    rom_info['region_code'] = prop_type
    
    type_display = (
        f"{Colors.WARNING}내수롬 (CN){Colors.ENDC}" if rom_type == 'china'
        else f"{Colors.OKGREEN}글로벌롬 (ROW){Colors.ENDC}"
    )
    print(f"\n{Colors.BOLD}[결과] 롬 타입:{Colors.ENDC} {type_display}")
    
    return rom_type, rom_info


