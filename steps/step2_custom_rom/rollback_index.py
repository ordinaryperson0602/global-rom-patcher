"""롤백 인덱스 관련 함수들"""
import os
import re
import sys
from pathlib import Path
from typing import Optional, Dict
from datetime import datetime

from config.colors import Colors
from config.paths import AVBTOOL_PY
from utils.avb_tools import get_image_avb_details
from utils.command import run_command
from utils.region_check import check_region_patterns


def extract_rollback_indices(rom_path: str) -> Optional[Dict[str, str]]:
    """
    롬파일에서 롤백 인덱스 추출
    
    Returns:
        {'boot': 'xxx', 'vbmeta_system': 'yyy'} 또는 실패 시 None
    """
    print(f"\n{Colors.BOLD}[추출] 롬파일 롤백 인덱스 확인 중...{Colors.ENDC}")
    
    image_dir = os.path.join(rom_path, 'image')
    rom_indices = {}
    
    # vbmeta_system.img 롤백 인덱스
    vbmeta_system_path = os.path.join(image_dir, 'vbmeta_system.img')
    if os.path.exists(vbmeta_system_path):
        details = get_image_avb_details(Path(vbmeta_system_path))
        if details and 'rollback_index' in details:
            rom_indices['vbmeta_system'] = details['rollback_index']
            print(f"  ✓ vbmeta_system RB: {details['rollback_index']}")
    
    # boot.img 롤백 인덱스
    boot_path = os.path.join(image_dir, 'boot.img')
    if os.path.exists(boot_path):
        details = get_image_avb_details(Path(boot_path))
        if details and 'rollback_index' in details:
            rom_indices['boot'] = details['rollback_index']
            print(f"  ✓ boot RB: {details['rollback_index']}")
    
    if not rom_indices:
        print(f"  {Colors.WARNING}⚠ 롤백 인덱스를 추출할 수 없습니다.{Colors.ENDC}")
        return None
    
    return rom_indices


def save_custom_rom_info_to_file(rom_path: str, rom_type: str, target_model: str, 
                                 rom_indices: Optional[Dict[str, str]], step1_output_dir: Optional[str] = None) -> None:
    """롬파일 정보를 txt 파일로 저장 (RSA 공식 롬 형식과 동일)"""
    print(f"\n{Colors.BOLD}[정보] 롬파일 분석 결과를 .txt 파일로 저장합니다...{Colors.ENDC}")
    
    now = datetime.now()
    date_str = now.strftime("%Y%m%d")
    time_str = now.strftime("%H%M%S")
    output_filename = f"CustomRomFile_Info_{target_model}_{date_str}_{time_str}.txt"
    
    # RSA 공식 롬파일처럼 STEP 1 백업 폴더에 저장
    if step1_output_dir and os.path.isdir(step1_output_dir):
        output_filepath = os.path.join(step1_output_dir, output_filename)
    else:
        # STEP 1 백업 폴더가 없으면 현재 디렉토리에 저장
        output_filepath = output_filename
    
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    
    # ========================================
    # vbmeta.img에서 모델 번호, 롬 버전, 국가 코드 추출
    # ========================================
    vbmeta_path = os.path.join(rom_path, 'image', 'vbmeta.img')
    model_number = target_model  # 기본값
    rom_version = "N/A"
    country_code = "ROW" if rom_type == 'global' else "PRC"
    
    if os.path.exists(vbmeta_path):
        try:
            cmd = [sys.executable, AVBTOOL_PY, 'info_image', '--image', vbmeta_path]
            success, output, _ = run_command(cmd, "vbmeta.img Prop 추출")
            
            if success and output:
                # fingerprint에서 모델, 롬 버전, 국가 코드 추출
                fingerprint_regex = re.compile(
                    r"'[^/]+/([^/]+)/[^:]+:[^/]+/((.*?)_(PRC|ROW)):user/release-keys'"
                )
                
                fingerprint_found = False
                for line in output.splitlines():
                    line_stripped = line.strip()
                    if line_stripped.startswith("Prop:") and "fingerprint" in line_stripped:
                        fingerprint_found = True
                        match = fingerprint_regex.search(line_stripped)
                        if match:
                            model_number = match.group(1)
                            rom_version = match.group(2)
                            country_code = match.group(4)
                            break  # 첫 번째 매칭만 사용
                        else:
                            # 디버깅: 정규표현식 매칭 실패
                            print(f"  {Colors.WARNING}⚠ 정규표현식 매칭 실패: {line_stripped[:100]}{Colors.ENDC}")
                
                if not fingerprint_found:
                    print(f"  {Colors.WARNING}⚠ vbmeta.img에서 fingerprint Prop을 찾을 수 없습니다.{Colors.ENDC}")
            else:
                print(f"  {Colors.WARNING}⚠ vbmeta.img Prop 추출 실패 (success={success}){Colors.ENDC}")
        except Exception as e:
            print(f"  {Colors.WARNING}⚠ vbmeta.img Prop 추출 중 오류: {e}{Colors.ENDC}")
    else:
        print(f"  {Colors.WARNING}⚠ vbmeta.img 파일을 찾을 수 없습니다: {vbmeta_path}{Colors.ENDC}")
    
    # ========================================
    # vendor_boot.img에서 지역 코드 추출
    # ========================================
    vendor_boot_path = os.path.join(rom_path, 'image', 'vendor_boot.img')
    hex_region_code = "N/A"
    
    if os.path.exists(vendor_boot_path):
        try:
            with open(vendor_boot_path, 'rb') as f:
                vendor_data = f.read()
            
            found_prc, found_iprc, found_row, found_irow = check_region_patterns(vendor_data)
            
            # 지역 코드 판정
            if found_irow:
                hex_region_code = "IROW (Hex)"
            elif found_row:
                hex_region_code = "ROW (Hex)"
            elif found_iprc:
                hex_region_code = "IPRC (Hex)"
            elif found_prc:
                hex_region_code = "PRC (Hex)"
        except Exception as e:
            print(f"  {Colors.WARNING}⚠ vendor_boot.img Hex 분석 중 오류: {e}{Colors.ENDC}")
    
    # ========================================
    # RSA 공식 롬 형식으로 파일 저장
    # ========================================
    content = (
        f"=== 장치 분석 정보 ===\n"
        f"분석 시간: {timestamp}\n"
        f"{'='*20}\n"
        f"1. 모델 번호 (vbmeta Prop): {model_number}\n"
        f"2. 롬 버전 (vbmeta Prop): {rom_version}\n"
        f"3. 지역 코드 (vendor_boot Hex): {hex_region_code}\n"
        f"4. 국가 코드 (vbmeta Prop): {country_code}\n"
        f"5. vbmeta_system 롤백 인덱스: {rom_indices.get('vbmeta_system', 'N/A') if rom_indices else 'N/A'}\n"
        f"6. boot 롤백 인덱스: {rom_indices.get('boot', 'N/A') if rom_indices else 'N/A'}\n"
    )
    
    try:
        with open(output_filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"  ✓ 분석 정보를 '{output_filename}' 파일에 저장했습니다.")
    except Exception as e:
        print(f"  {Colors.WARNING}⚠ 정보 파일 저장 중 오류: {e}{Colors.ENDC}")

