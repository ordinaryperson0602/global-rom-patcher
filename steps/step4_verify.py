"""STEP 4: 패치 검증 - 실제 코드"""
# 표준 라이브러리
import os
import re
import shutil
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Dict, List, Optional

# 로컬 모듈
from config.colors import Colors
from config.paths import CURRENT_DIR, TOOL_DIR, VERIFY_TEMP_DIR, KNOWN_SIGNING_KEYS
from config.constants import UIConstants
from config.messages import TitleMessages
from core.progress import init_step_progress, update_sub_task, global_print_progress, global_end_progress
from core.logger import log_error
from utils.ui import show_popup, get_platform_executable
from utils.command import run_external_command
from utils.avb_tools import get_image_avb_details
from utils.region_check import check_region_in_image


# 이미지 파일 매직 넘버
IMAGE_MAGIC_NUMBERS = {
    "boot.img": b'ANDROID!',
    "vendor_boot.img": b'VNDRBOOT',
    "vbmeta.img": b'AVB0',
    "vbmeta_system.img": b'AVB0'
}

# 파일 크기 임계값 (bytes)
MIN_IMAGE_SIZE = 1024  # 1KB


def check_for_kernelsu_strings(kernel_file_path: Path) -> bool:
    """커널 파일에서 KernelSU 시그니처 확인"""
    if not kernel_file_path.exists():
        print(f"  [오류] 커널 파일을 찾을 수 없습니다: '{kernel_file_path}'", file=sys.stderr)
        return False
    try:
        content = kernel_file_path.read_bytes()
        return b"CONFIG_KSU_SUSFS" in content or b"susfs:" in content
    except Exception as e:
        error_msg = f"커널 파일 바이너리 스캔 중 예외 발생: {e}"
        print(f"  [오류] {error_msg}", file=sys.stderr)
        log_error(error_msg, exception=e, context="STEP 4 - 커널 스캔")
        return False


def run_and_capture(cmd_params: List[str]) -> Optional[str]:
    """STDOUT 캡처"""
    env = os.environ.copy()
    env['PATH'] = str(TOOL_DIR) + os.pathsep + env['PATH']
    try:
        process = subprocess.run(
            cmd_params, check=True, capture_output=True, text=True,
            encoding='utf-8', errors='ignore', env=env
        )
        return process.stdout.strip()
    except:
        return None


def parse_digest(stdout: Optional[str], partition_name: str) -> Optional[str]:
    """print_partition_digests 출력 파싱"""
    if not stdout:
        return None
    match = re.search(rf"^\s*{re.escape(partition_name)}:\s*\(?([0-9a-fA-F]+)\)?\s*$", stdout, re.MULTILINE)
    if match:
        return match.group(1)
    return None


def verify_region_code(image_dir: Path) -> bool:
    """vendor_boot 리전 코드 검증"""
    from core.logger import info, log_validation
    
    info("vendor_boot 리전 코드 검증 시작", image_dir=str(image_dir))
    vb_path = image_dir / "vendor_boot.img"
    if not vb_path.exists():
        log_validation("vendor_boot.img 존재 여부", False, f"파일 없음: {vb_path}")
        print(f"  {Colors.FAIL}[실패] 'vendor_boot.img' 파일을 찾을 수 없습니다.{Colors.ENDC}")
        return False
    try:
        content = vb_path.read_bytes()
        prc_found, row_found = check_region_in_image(content)
        
        info(f"리전 코드 검사 결과", prc_found=prc_found, row_found=row_found)
        
        if prc_found and not row_found:
            log_validation("vendor_boot 리전 코드", True, "PRC/IPRC 코드 확인됨")
            print(f"  > 'vendor_boot.img'에 {Colors.OKGREEN}PRC/IPRC{Colors.ENDC} 코드가 확인되었습니다.")
            return True
        elif row_found:
            log_validation("vendor_boot 리전 코드", False, "ROW/IROW 코드 남아있음")
            print(f"  {Colors.FAIL}[실패] 'vendor_boot.img'에 여전히 ROW/IROW 코드가 남아있습니다.{Colors.ENDC}")
            return False
        else:
            log_validation("vendor_boot 리전 코드", False, "PRC/IPRC 코드 없음")
            print(f"  {Colors.FAIL}[실패] 'vendor_boot.img'에서 PRC/IPRC 코드를 찾을 수 없습니다.{Colors.ENDC}")
            return False
    except Exception as e:
        error_msg = f"'vendor_boot.img' 파일 읽기 중 오류: {e}"
        print(f"  {Colors.FAIL}[오류] {error_msg}{Colors.ENDC}")
        log_error(error_msg, exception=e, context="STEP 4 - vendor_boot 읽기")
        return False


def verify_image_signing(image_path: Path, image_name: str) -> bool:
    """이미지 서명 키 검증 (공통 로직)"""
    from core.logger import info, log_validation
    
    info(f"이미지 서명 검증 시작", image=image_name, path=str(image_path))
    
    if not image_path.exists():
        log_validation(f"{image_name} 존재 여부", False, f"파일 없음: {image_path}")
        print(f"  {Colors.FAIL}[실패] '{image_name}' 파일을 찾을 수 없습니다.{Colors.ENDC}")
        return False
    
    details = get_image_avb_details(image_path)
    
    if not details or 'pubkey_sha1' not in details:
        print(f"  {Colors.FAIL}[실패] '{image_name}'의 서명 정보를 읽을 수 없습니다.{Colors.ENDC}")
        return False
    
    found_hash = details['pubkey_sha1']
    test_key_hashes = list(KNOWN_SIGNING_KEYS.keys())
    
    info(f"서명 키 검사", image=image_name, found_hash=found_hash[:16])
    
    if found_hash in test_key_hashes:
        log_validation(f"{image_name} 서명 키", True, f"테스트 키로 서명됨: {found_hash[:16]}")
        print(f"  > '{image_name}'가 {Colors.OKGREEN}테스트 키{Colors.ENDC}({found_hash[:10]}...)로 서명되었습니다.")
        return True
    else:
        log_validation(f"{image_name} 서명 키", False, f"알 수 없는 키: {found_hash[:16]}")
        print(f"  {Colors.FAIL}[실패] '{image_name}'가 알 수 없는 키({found_hash[:10]}...)로 서명되었습니다.{Colors.ENDC}")
        return False


def verify_signing_key(image_dir: Path) -> bool:
    """vbmeta 서명 키 검증"""
    return verify_image_signing(image_dir / "vbmeta.img", "vbmeta.img")


def verify_vbmeta_system_signing(image_dir: Path) -> bool:
    """vbmeta_system 서명 키 검증"""
    return verify_image_signing(image_dir / "vbmeta_system.img", "vbmeta_system.img")


def verify_partition_hash(image_dir: Path, partition_name: str) -> bool:
    """파티션 해시 검증 (공통 로직)"""
    partition_path = image_dir / f"{partition_name}.img"
    vm_path = image_dir / "vbmeta.img"
    
    if not (partition_path.exists() and vm_path.exists()):
        print(f"  {Colors.FAIL}[실패] '{partition_name}.img' 또는 'vbmeta.img' 파일을 찾을 수 없습니다.{Colors.ENDC}")
        return False
    
    print(f"  > 'avbtool print_partition_digests' 명령어로 {partition_name} 해시 비교 중...")
    
    cmd_partition = [sys.executable, str(TOOL_DIR / "avbtool.py"), "print_partition_digests", "--image", str(partition_path)]
    cmd_vm = [sys.executable, str(TOOL_DIR / "avbtool.py"), "print_partition_digests", "--image", str(vm_path)]
    
    stdout_partition = run_and_capture(cmd_partition)
    stdout_vm = run_and_capture(cmd_vm)
    
    hash_partition = parse_digest(stdout_partition, partition_name)
    hash_vm = parse_digest(stdout_vm, partition_name)
    
    if not hash_partition:
        print(f"  {Colors.FAIL}[실패] '{partition_name}.img'의 다이제스트를 계산할 수 없습니다.{Colors.ENDC}")
        return False
    if not hash_vm:
        print(f"  {Colors.FAIL}[실패] 'vbmeta.img'에서 '{partition_name}'의 다이제스트를 찾을 수 없습니다.{Colors.ENDC}")
        return False
    
    if hash_partition == hash_vm:
        print(f"  > 'vbmeta.img'의 해시({Colors.OKGREEN}{hash_vm[:10]}...{Colors.ENDC})가 '{partition_name}.img'의 해시와 {Colors.OKGREEN}일치{Colors.ENDC}합니다.")
        return True
    else:
        print(f"  {Colors.FAIL}[실패] 해시 불일치!{Colors.ENDC}")
        return False


def verify_vbmeta_hash(image_dir: Path) -> bool:
    """vbmeta 해시 일치 검증 (vendor_boot)"""
    return verify_partition_hash(image_dir, "vendor_boot")


def verify_boot_hash(image_dir: Path) -> bool:
    """boot.img의 vbmeta 해시 일치 검증"""
    return verify_partition_hash(image_dir, "boot")


def verify_rollback_index(image_dir: Path, expected_rb_indices: Dict[str, str], 
                         rom_indices: Optional[Dict[str, str]]) -> bool:
    """롤백 인덱스 검증"""
    if not expected_rb_indices:
        print(f"  > ARB 롤백 패치가 요청되지 않았습니다. {Colors.OKCYAN}[정상 건너뜀]{Colors.ENDC}")
        if not rom_indices:
            print(f"  > {Colors.WARNING}롬파일 인덱스 정보가 없어 검증 생략.{Colors.ENDC}")
            return True
        
        boot_details = get_image_avb_details(image_dir / "boot.img")
        vbm_sys_details = get_image_avb_details(image_dir / "vbmeta_system.img")
        
        actual_boot_rb = boot_details.get('rollback_index') if boot_details else None
        actual_vbm_sys_rb = vbm_sys_details.get('rollback_index') if vbm_sys_details else None
        
        rom_boot_rb = rom_indices.get('boot')
        rom_vbm_sys_rb = rom_indices.get('vbmeta_system')
        
        all_ok = True
        if rom_boot_rb and actual_boot_rb != rom_boot_rb:
            print(f"  {Colors.FAIL}[실패] boot: 인덱스가 롬({rom_boot_rb})과 다름! (실제: {actual_boot_rb}){Colors.ENDC}")
            all_ok = False
        if rom_vbm_sys_rb and actual_vbm_sys_rb != rom_vbm_sys_rb:
            print(f"  {Colors.FAIL}[실패] vbmeta_system: 인덱스가 롬({rom_vbm_sys_rb})과 다름! (실제: {actual_vbm_sys_rb}){Colors.ENDC}")
            all_ok = False
        
        if all_ok:
            print(f"  > 롤백 인덱스가 롬파일 원본과 {Colors.OKGREEN}일치{Colors.ENDC}합니다.")
        return all_ok
    
    print("  > ARB 롤백 패치가 감지되었습니다. 패치된 인덱스 값을 검사합니다.")
    boot_details = get_image_avb_details(image_dir / "boot.img")
    vbm_sys_details = get_image_avb_details(image_dir / "vbmeta_system.img")
    
    actual_boot_rb = boot_details.get('rollback_index') if boot_details else None
    actual_vbm_sys_rb = vbm_sys_details.get('rollback_index') if vbm_sys_details else None
    
    all_ok = True
    
    if 'boot' in expected_rb_indices:
        expected = expected_rb_indices['boot']
        if actual_boot_rb == expected:
            print(f"  > boot: 롤백 인덱스가 예상 값({Colors.OKGREEN}{expected}{Colors.ENDC})과 일치합니다.")
        else:
            print(f"  {Colors.FAIL}[실패] boot: 롤백 인덱스 불일치{Colors.ENDC}")
            all_ok = False
    
    if 'vbmeta_system' in expected_rb_indices:
        expected = expected_rb_indices['vbmeta_system']
        if actual_vbm_sys_rb == expected:
            print(f"  > vbmeta_system: 롤백 인덱스가 예상 값({Colors.OKGREEN}{expected}{Colors.ENDC})과 일치합니다.")
        else:
            print(f"  {Colors.FAIL}[실패] vbmeta_system: 롤백 인덱스 불일치{Colors.ENDC}")
            all_ok = False
    
    return all_ok


def verify_file_integrity(image_dir: Path) -> bool:
    """이미지 파일 무결성 검증"""
    all_ok = True
    
    for img_name, magic in IMAGE_MAGIC_NUMBERS.items():
        img_path = image_dir / img_name
        
        if not img_path.exists():
            print(f"  {Colors.FAIL}[실패] '{img_name}' 파일을 찾을 수 없습니다.{Colors.ENDC}")
            all_ok = False
            continue
        
        try:
            file_size = img_path.stat().st_size
            
            # 파일 크기 검사 (너무 작으면 손상된 것)
            if file_size < MIN_IMAGE_SIZE:
                print(f"  {Colors.FAIL}[실패] '{img_name}'이(가) 너무 작습니다 ({file_size} bytes).{Colors.ENDC}")
                all_ok = False
                continue
            
            # 매직 넘버 확인
            with open(img_path, 'rb') as f:
                header = f.read(512)  # 처음 512바이트 읽기
                
                if magic not in header:
                    print(f"  {Colors.FAIL}[실패] '{img_name}'의 헤더가 올바르지 않습니다 (매직: {magic}).{Colors.ENDC}")
                    all_ok = False
                    continue
            
            print(f"  > '{img_name}': {Colors.OKGREEN}무결성 확인{Colors.ENDC} (크기: {file_size:,} bytes)")
        
        except Exception as e:
            print(f"  {Colors.FAIL}[오류] '{img_name}' 검사 중 예외: {e}{Colors.ENDC}")
            all_ok = False
    
    return all_ok


def verify_kernelsu(image_dir: Path, want_root: bool) -> bool:
    """KernelSU 패치 검증"""
    if not want_root:
        print(f"  > KernelSU 패치가 요청되지 않았습니다. {Colors.OKCYAN}[정상 건너뜀]{Colors.ENDC}")
        return True
    
    print("  > 'boot.img'에서 'kernel' 파일을 추출하여 KernelSU 시그니처를 스캔합니다.")
    boot_path = image_dir / "boot.img"
    boot_tool = get_platform_executable("magiskboot")
    
    if VERIFY_TEMP_DIR.exists():
        shutil.rmtree(VERIFY_TEMP_DIR)
    VERIFY_TEMP_DIR.mkdir()
    
    original_cwd = Path.cwd()
    success = False
    
    try:
        shutil.copy(boot_path, VERIFY_TEMP_DIR / "boot.img")
        os.chdir(VERIFY_TEMP_DIR)
        
        if not run_external_command([str(boot_tool), "unpack", "boot.img"], suppress_output=True):
            raise RuntimeError("magiskboot unpack 실패")
        
        kernel_path = VERIFY_TEMP_DIR / "kernel"
        if not kernel_path.exists():
            raise RuntimeError("kernel 파일 추출 실패")
        
        kernelsu_found = check_for_kernelsu_strings(kernel_path)
        
        if kernelsu_found:
            print(f"  > 커널 바이너리에서 {Colors.OKGREEN}'CONFIG_KSU_SUSFS' 또는 'susfs:'{Colors.ENDC} 문자열을 확인했습니다.")
            success = True
        else:
            print(f"  {Colors.FAIL}[실패] 커널 바이너리에서 KernelSU 관련 시그니처 문자열을 찾을 수 없습니다.{Colors.ENDC}")
            success = False
    
    except Exception as e:
        print(f"  {Colors.FAIL}[오류] boot.img 검증 중 예외 발생: {e}{Colors.ENDC}")
        success = False
    finally:
        os.chdir(original_cwd)
        if VERIFY_TEMP_DIR.exists():
            shutil.rmtree(VERIFY_TEMP_DIR)
    
    return success


def run_check(step_name: str, func, *args) -> bool:
    """검증 함수 실행 래퍼"""
    print(f"{Colors.BOLD}--- {step_name} ---{Colors.ENDC}")
    try:
        success = func(*args)
        if success:
            print(f"  > {Colors.OKGREEN}[검증 통과]{Colors.ENDC}\n")
            return True
        else:
            print(f"  > {Colors.FAIL}[검증 실패]{Colors.ENDC}\n")
            return False
    except Exception as e:
        print(f"  > {Colors.FAIL}[치명적 오류] {e}{Colors.ENDC}\n", file=sys.stderr)
        return False


def run_step_4(rom_path: str, want_root: bool, expected_rb_indices: Dict[str, str],
               rom_indices: Optional[Dict[str, str]]) -> bool:
    """STEP 4 메인 로직"""
    image_dir = Path(rom_path) / "image"
    results = {"success": 0, "fail": 0}
    
    task_names = [
        "파일 무결성 검증",
        "vendor_boot 검증",
        "vbmeta 검증",
        "vbmeta_system 검증",
        "boot 검증",
        "해시 검증",
        "롤백 인덱스 검증",
        "루팅 검증"
    ]
    init_step_progress(4, 8, task_names)
    
    print("=" * 60)
    print(f"{Colors.BOLD}STEP 4: 이미지 패치 검증 프로그램{Colors.ENDC}")
    print(f"검증 대상 폴더: {image_dir}")
    print("=" * 60)
    
    if not image_dir.is_dir():
        print(f"{Colors.FAIL}[!] 오류: 'image' 폴더를 찾을 수 없습니다: {image_dir}{Colors.ENDC}", file=sys.stderr)
        show_popup("STEP 4 오류 - NG", f"'image' 폴더를 찾을 수 없습니다:\n{image_dir}", 
                  exit_on_close=False, icon=UIConstants.ICON_ERROR)
        print(f"\n{Colors.OKCYAN}메인 메뉴로 돌아갑니다...{Colors.ENDC}")
        input("\nEnter 키를 누르면 메인 메뉴로 돌아갑니다...")
        return False
    
    print("--- [정보] STEP 3의 작업 결과(예상 값) 설정 완료 ---")
    if expected_rb_indices:
        print(f"  > {Colors.WARNING}ARB 패치 검증 대상: {list(expected_rb_indices.keys())}{Colors.ENDC}\n")
    else:
        print(f"  > {Colors.OKGREEN}ARB 패치가 예상되지 않습니다.{Colors.ENDC}\n")
    
    print(f"  > KernelSU 루팅 선택 여부: {Colors.OKCYAN}{want_root}{Colors.ENDC}\n")
    
    # 검증 1: 파일 무결성
    update_sub_task(0, 'in_progress')
    global_print_progress(1, 8, "STEP 4")
    if run_check("검증 1: 파일 무결성 (크기 및 헤더)", verify_file_integrity, image_dir):
        results["success"] += 1
    else:
        results["fail"] += 1
    update_sub_task(0, 'done')
    
    # 검증 2: vendor_boot 리전 코드
    update_sub_task(1, 'in_progress')
    global_print_progress(2, 8, "STEP 4")
    if run_check("검증 2: 리전 코드 (PRC) 변경", verify_region_code, image_dir):
        results["success"] += 1
    else:
        results["fail"] += 1
    update_sub_task(1, 'done')
    
    # 검증 3: vbmeta 서명 키
    update_sub_task(2, 'in_progress')
    global_print_progress(3, 8, "STEP 4")
    if run_check("검증 3: vbmeta 서명 키 (TestKey)", verify_signing_key, image_dir):
        results["success"] += 1
    else:
        results["fail"] += 1
    update_sub_task(2, 'done')
    
    # 검증 4: vbmeta_system 서명 키
    update_sub_task(3, 'in_progress')
    global_print_progress(4, 8, "STEP 4")
    if run_check("검증 4: vbmeta_system 서명 키 (TestKey)", verify_vbmeta_system_signing, image_dir):
        results["success"] += 1
    else:
        results["fail"] += 1
    update_sub_task(3, 'done')
    
    # 검증 5: boot 해시
    update_sub_task(4, 'in_progress')
    global_print_progress(5, 8, "STEP 4")
    if run_check("검증 5: boot.img 해시 일치", verify_boot_hash, image_dir):
        results["success"] += 1
    else:
        results["fail"] += 1
    update_sub_task(4, 'done')
    
    # 검증 6: vendor_boot 해시
    update_sub_task(5, 'in_progress')
    global_print_progress(6, 8, "STEP 4")
    if run_check("검증 6: vendor_boot.img 해시 일치", verify_vbmeta_hash, image_dir):
        results["success"] += 1
    else:
        results["fail"] += 1
    update_sub_task(5, 'done')
    
    # 검증 7: 롤백 인덱스
    update_sub_task(6, 'in_progress')
    global_print_progress(7, 8, "STEP 4")
    if run_check("검증 7: 롤백 인덱스(ARB) 일치", verify_rollback_index, image_dir, expected_rb_indices, rom_indices):
        results["success"] += 1
    else:
        results["fail"] += 1
    update_sub_task(6, 'done')
    
    # 검증 8: KernelSU
    update_sub_task(7, 'in_progress')
    global_print_progress(8, 8, "STEP 4")
    if run_check("검증 8: KernelSU 패치", verify_kernelsu, image_dir, want_root):
        results["success"] += 1
    else:
        results["fail"] += 1
    update_sub_task(7, 'done')
    
    global_end_progress()
    print("=" * 60)
    print(f"{Colors.BOLD}🎉 검증 완료 - 최종 결과{Colors.ENDC}")
    print(f"  {Colors.OKGREEN}성공: {results['success']} 항목{Colors.ENDC}")
    print(f"  {Colors.FAIL if results['fail'] > 0 else Colors.WARNING}실패: {results['fail']} 항목{Colors.ENDC}")
    
    if results['fail'] > 0:
        msg = f"하나 이상의 검증에 실패했습니다!\n\n성공: {results['success']}, 실패: {results['fail']}\n\n'STEP 3' 프로그램을 다시 실행하거나 'image' 폴더의 .original 파일로 복구하십시오."
        print(f"\n{Colors.FAIL}[!!!] {msg}{Colors.ENDC}")
        show_popup("검증 실패 - NG", msg, icon=UIConstants.ICON_ERROR)
        raise Exception("STEP 4 검증 실패")
    else:
        print(f"\n{Colors.OKGREEN}🎉 모든 검증을 성공적으로 통과했습니다! 패치가 완료되었습니다.{Colors.ENDC}")
