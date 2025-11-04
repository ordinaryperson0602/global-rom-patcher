"""STEP 3: 롬파일 패치 (ARB, KSU) - 실제 코드"""
# 표준 라이브러리
import os
import platform
import re
import shutil
import subprocess
import sys
import traceback
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# 로컬 모듈
from config.colors import Colors
from config.paths import (
    CURRENT_DIR, TOOL_DIR, ROOTING_TOOL_DIR, KNOWN_SIGNING_KEYS, TEMP_WORK_DIR, PYTHON_EXE
)
from config.constants import GKI_REPO_URL, GKI_TAG, KSU_MANAGER_REPO, KSU_MANAGER_TAG, UIConstants
from config.messages import ErrorMessages, TitleMessages
from core.progress import init_step_progress, update_sub_task, global_print_progress, global_end_progress
from core.logger import log_command_output, log_error
from utils.ui import show_popup, get_platform_executable
from utils.command import run_external_command
from utils.avb_tools import get_image_avb_details, find_signing_key

def extract_kernel_version_from_file(kernel_file_path: Path) -> Optional[str]:
    """커널 파일에서 버전 추출"""
    if not kernel_file_path.exists():
        print(f"  [오류] 커널 파일을 찾을 수 없습니다: '{kernel_file_path}'", file=sys.stderr)
        return None
    try:
        content = kernel_file_path.read_bytes()
        potential_strings = re.findall(b'[ -~]{10,}', content)
        found_version = None
        for string_bytes in potential_strings:
            try:
                line = string_bytes.decode('ascii', errors='ignore')
                if 'Linux version ' in line:
                    base_version_match = re.search(r'(\d+\.\d+\.\d+)', line)
                    if base_version_match:
                        found_version = base_version_match.group(1)
                        break
            except UnicodeDecodeError:
                continue
        if found_version:
            return found_version
        else:
            print("  [오류] 커널 파일에서 'Linux version' 문자열을 찾거나 파싱할 수 없습니다.", file=sys.stderr)
            return None
    except Exception as e:
        error_msg = f"커널 버전 추출 중 예외 발생: {e}"
        print(f"  [오류] {error_msg}", file=sys.stderr)
        log_error(error_msg, exception=e, context="STEP 3 - 커널 버전 추출")
        return None


def patch_region_identifiers(original_vb_path: Path, target_vb_path: Path) -> bool:
    """vendor_boot ROW -> PRC 패치"""
    from config.constants import HEX_ROW, HEX_IROW, HEX_PRC, HEX_IPRC
    
    patterns_to_replace = {
        HEX_ROW: HEX_PRC,
        HEX_IROW: HEX_IPRC
    }
    
    try:
        content = original_vb_path.read_bytes()
        
        modified_content = content
        replacements_made = 0
        for old_bytes, new_bytes in patterns_to_replace.items():
            count = modified_content.count(old_bytes)
            if count > 0:
                modified_content = modified_content.replace(old_bytes, new_bytes)
                replacements_made += count
        
        if replacements_made == 0:
            global_end_progress()
            print(f"\n{Colors.FAIL}[오류 - NG] vendor_boot에서 ROW/IROW 패턴을 찾을 수 없습니다.{Colors.ENDC}", file=sys.stderr)
            show_popup("오류 - NG",
                      "vendor_boot 이미지에서 ROW/IROW 패턴을 찾을 수 없습니다.\n\n"
                      "STEP 2 검증을 통과했는데 패턴이 없다면\n"
                      "파일이 손상되었거나 지원하지 않는 형식입니다.",
                      icon=UIConstants.ICON_ERROR)
            return False
        
        print(f"  {Colors.OKGREEN}패치 적용 후 파일 저장 중...{Colors.ENDC}")
        target_vb_path.write_bytes(modified_content)
        print(f"  {Colors.OKGREEN}✓ ROW → PRC 패치 완료! ({replacements_made}개 항목){Colors.ENDC}\n")
        return True
    except Exception as e:
        global_end_progress()
        error_msg = f"vendor_boot 파일 패치 중 예외 발생: {e}"
        print(f"\n  {Colors.FAIL}[오류] {error_msg}{Colors.ENDC}", file=sys.stderr)
        log_error(error_msg, exception=e, context="STEP 3 - vendor_boot 패치")
        return False


def sign_image_with_footer(target_image: Path, info_source_image: Path,
                           override_rollback_index: Optional[str] = None) -> bool:
    """이미지에 AVB 푸터/서명 추가"""
    img_info = get_image_avb_details(info_source_image)
    
    required_keys = ['partition_size', 'name', 'rollback_index', 'salt', 'algorithm']
    if not img_info or not all(key in img_info for key in required_keys):
        global_end_progress()
        print(
            f"\n  {Colors.FAIL}[오류] '{info_source_image.name}' 분석 실패. "
            f"서명에 필요한 정보가 부족합니다.{Colors.ENDC}",
            file=sys.stderr
        )
        return False
    
    rollback_index_to_use = override_rollback_index if override_rollback_index else img_info['rollback_index']
    
    cmd_add_footer = [
        PYTHON_EXE, str(TOOL_DIR / "avbtool.py"), "add_hash_footer",
        "--image", str(target_image),
        "--partition_size", img_info['partition_size'],
        "--partition_name", img_info['name'],
        "--rollback_index", rollback_index_to_use,
        "--salt", img_info['salt'],
        *(img_info.get('prop_args', []))
    ]
    
    original_algorithm = img_info['algorithm'].upper()
    if original_algorithm != 'NONE':
        if 'pubkey_sha1' not in img_info:
            global_end_progress()
            print(f"\n  {Colors.FAIL}[오류] 서명이 필요한 이미지이나 공개 키 정보(pubkey_sha1)가 없습니다.{Colors.ENDC}", file=sys.stderr)
            return False
        key_file = find_signing_key(img_info['pubkey_sha1'])
        if not key_file:
            return False
        cmd_add_footer.extend(["--key", str(key_file), "--algorithm", img_info['algorithm']])
    else:
        cmd_add_footer.extend(["--algorithm", "NONE"])
    
    return run_external_command(cmd_add_footer, suppress_output=True)


def perform_boot_patching(image_dir: Path, rb_indices: Optional[Dict[str, str]],
                         current_step: int, total_steps: int) -> int:
    """boot.img를 GKI KernelSU로 패치"""
    boot_tool = get_platform_executable("magiskboot")
    dl_tool = get_platform_executable("fetch")
    
    boot_path = image_dir / "boot.img"
    boot_bak_path = image_dir / "boot.img.original"
    
    if not boot_bak_path.exists():
        global_end_progress()
        print(f"\n{Colors.FAIL}[!] 'boot.img.original' 백업이 없습니다.{Colors.ENDC}", file=sys.stderr)
        return -1
    
    if TEMP_WORK_DIR.exists():
        shutil.rmtree(TEMP_WORK_DIR)
    TEMP_WORK_DIR.mkdir()
    
    original_cwd = Path.cwd()
    os.chdir(TEMP_WORK_DIR)
    
    boot_patched_path = TEMP_WORK_DIR / "boot.img.patched"
    
    try:
        shutil.copy(boot_bak_path, TEMP_WORK_DIR / "boot.img")
        extracted_kernel_path = TEMP_WORK_DIR / "kernel"
        
        current_step += 1
        print(f"  [{current_step}/{total_steps}] 부트 이미지 압축 해제 중...")
        if not run_external_command([str(boot_tool), "unpack", "boot.img"], suppress_output=True):
            raise RuntimeError("magiskboot unpack 실패")
        if not extracted_kernel_path.exists():
            global_end_progress()
            print(f"\n  {Colors.FAIL}[!] boot.img 압축 해제 실패 (kernel 파일 없음).{Colors.ENDC}")
            return -1
        
        current_step += 1
        print(f"  [{current_step}/{total_steps}] 대상 커널 버전 확인 중...")
        kernel_version_str = extract_kernel_version_from_file(extracted_kernel_path)
        if not kernel_version_str:
            global_end_progress()
            print(f"\n  {Colors.FAIL}[!] 커널 버전 추출 실패.{Colors.ENDC}")
            return -1
        if not re.match(r"\d+\.\d+\.\d+", kernel_version_str):
            global_end_progress()
            print(f"\n  {Colors.FAIL}[!] 유효하지 않은 커널 버전 형식: '{kernel_version_str}'{Colors.ENDC}")
            return -1
        
        current_step += 1
        print(f"  [{current_step}/{total_steps}] GKI 커널 ({kernel_version_str}) 다운로드 중...")
        asset_filter = f".*{kernel_version_str}.*AnyKernel3.zip"
        fetch_cmd = [str(dl_tool), "--repo", GKI_REPO_URL, "--tag", GKI_TAG, "--release-asset", asset_filter, "."]
        if not run_external_command(fetch_cmd, suppress_output=True):
            raise RuntimeError("GKI 커널 다운로드 실패")
        zip_files = list(Path(".").glob(f"*{kernel_version_str}*AnyKernel3.zip"))
        if not zip_files:
            global_end_progress()
            print(f"\n  {Colors.FAIL}[!] 커널 {kernel_version_str}용 Zip 다운로드 실패.{Colors.ENDC}")
            return -1
        shutil.move(zip_files[0], "AnyKernel3.zip")
        
        current_step += 1
        print(f"  [{current_step}/{total_steps}] 새 커널 이미지 추출 중...")
        kernel_extract_dir = TEMP_WORK_DIR / "gki_kernel"
        with zipfile.ZipFile("AnyKernel3.zip", 'r') as zf:
            zf.extractall(kernel_extract_dir)
        new_kernel_image = kernel_extract_dir / "Image"
        if not new_kernel_image.exists():
            global_end_progress()
            print(f"\n  {Colors.FAIL}[!] 다운로드한 Zip 파일에서 'Image' 파일을 찾을 수 없습니다.{Colors.ENDC}")
            return -1
        
        current_step += 1
        print(f"  [{current_step}/{total_steps}] 커널 교체 및 재패키징 중...")
        shutil.move(str(new_kernel_image), extracted_kernel_path)
        if not run_external_command([str(boot_tool), "repack", "boot.img"], suppress_output=True):
            raise RuntimeError("magiskboot repack 실패")
        repacked_boot = TEMP_WORK_DIR / "new-boot.img"
        if not repacked_boot.exists():
            global_end_progress()
            print(f"\n  {Colors.FAIL}[!] 부트 이미지 재패키징 실패.{Colors.ENDC}")
            return -1
        shutil.move(repacked_boot, boot_patched_path)
        
        current_step += 1
        print(f"  [{current_step}/{total_steps}] 부트 이미지 서명/롤백 적용 중...")
        boot_rb_index_to_set = rb_indices.get('boot') if rb_indices else None
        if not sign_image_with_footer(boot_patched_path, boot_bak_path, override_rollback_index=boot_rb_index_to_set):
            raise RuntimeError("패치된 boot.img 서명/롤백 적용 실패")
        
        current_step += 1
        print(f"  [{current_step}/{total_steps}] KernelSU Manager APK 다운로드 중...")
        if not list(CURRENT_DIR.glob("KernelSU*.apk")):
            ksu_apk_cmd = [
                str(dl_tool), "--repo", f"https://github.com/{KSU_MANAGER_REPO}",
                "--tag", KSU_MANAGER_TAG, "--release-asset", ".*\\.apk", str(CURRENT_DIR)
            ]
            if not run_external_command(ksu_apk_cmd, suppress_output=True):
                sys.stderr.write(f"\n{Colors.WARNING}[경고] KernelSU Manager APK 다운로드에 실패했습니다. (무시하고 계속함){Colors.ENDC}\n")
                sys.stderr.flush()
        
        shutil.move(boot_patched_path, boot_path)
        return current_step
    
    except Exception as e:
        global_end_progress()
        error_msg = f"부트 패치 중 예외 발생: {e}"
        print(f"\n  {Colors.FAIL}[오류] {error_msg}{Colors.ENDC}", file=sys.stderr)
        log_error(error_msg, exception=e, context="STEP 3 - boot 패치")
        return -1
    finally:
        os.chdir(original_cwd)
        if TEMP_WORK_DIR.exists():
            shutil.rmtree(TEMP_WORK_DIR)


def apply_rollback_indices(image_dir: Path, rb_indices: Dict[str, str],
                           is_rooting: bool, current_step: int, total_steps: int) -> int:
    """롤백 인덱스 적용"""
    if 'vbmeta_system' in rb_indices:
        current_step += 1
        print(f"  [{current_step}/{total_steps}] vbmeta_system 롤백 인덱스 적용 중...")
        vbmeta_sys_path = image_dir / "vbmeta_system.img"
        vbmeta_sys_bak = image_dir / "vbmeta_system.img.original"
        if not vbmeta_sys_bak.exists():
            sys.stderr.write(f"\n{Colors.WARNING}[경고] '{vbmeta_sys_bak.name}' 백업이 없습니다.{Colors.ENDC}\n")
            sys.stderr.flush()
        else:
            vm_sys_info = get_image_avb_details(vbmeta_sys_bak)
            required_keys = ['algorithm', 'pubkey_sha1']
            if not vm_sys_info or not all(key in vm_sys_info for key in required_keys):
                sys.stderr.write(f"\n{Colors.FAIL}[오류] '{vbmeta_sys_bak.name}' 분석 실패.{Colors.ENDC}\n")
                sys.stderr.flush()
            else:
                key_file = find_signing_key(vm_sys_info['pubkey_sha1'])
                new_rb_val = rb_indices['vbmeta_system']
                if key_file:
                    cmd_make_vbmeta_sys = [
                        PYTHON_EXE, str(TOOL_DIR / "avbtool.py"), "make_vbmeta_image",
                        "--output", str(vbmeta_sys_path), "--key", str(key_file),
                        "--algorithm", vm_sys_info['algorithm'], "--rollback_index", new_rb_val,
                        "--padding_size", "4096",
                        "--include_descriptors_from_image", str(vbmeta_sys_bak)
                    ]
                    if not run_external_command(cmd_make_vbmeta_sys, suppress_output=True):
                        sys.stderr.write(f"\n{Colors.FAIL}[오류] 'vbmeta_system.img' 롤백 인덱스 갱신 실패.{Colors.ENDC}\n")
                        sys.stderr.flush()
    
    if 'boot' in rb_indices:
        if not is_rooting:
            current_step += 1
            print(f"  [{current_step}/{total_steps}] boot 롤백 인덱스 적용 중...")
            boot_path = image_dir / "boot.img"
            boot_bak_path = image_dir / "boot.img.original"
            new_rb_val = rb_indices['boot']
            if not boot_bak_path.exists():
                sys.stderr.write(f"\n{Colors.WARNING}[경고] '{boot_bak_path.name}' 백업이 없습니다.{Colors.ENDC}\n")
                sys.stderr.flush()
            else:
                shutil.copy2(boot_bak_path, boot_path)
                if not sign_image_with_footer(boot_path, boot_bak_path, override_rollback_index=new_rb_val):
                    sys.stderr.write(f"\n{Colors.FAIL}[오류] 'boot.img' 롤백 인덱스 갱신 실패.{Colors.ENDC}\n")
                    sys.stderr.flush()
    
    return current_step


# ============================================================================
# start_modification Helper Functions (리팩토링)
# ============================================================================

def _check_image_directory(rom_base_directory: str) -> Optional[Path]:
    """image 디렉토리 확인"""
    image_dir = Path(rom_base_directory) / "image"
    if not image_dir.is_dir():
        print(f"{Colors.FAIL}[!] 오류: 'image' 폴더를 찾을 수 없습니다: {image_dir}{Colors.ENDC}", file=sys.stderr)
        show_popup("STEP 3 오류 - NG", f"필수 'image' 폴더를 찾을 수 없습니다:\n{image_dir}",
                  exit_on_close=False, icon=UIConstants.ICON_ERROR)
        print(f"\n{Colors.OKCYAN}메인 메뉴로 돌아갑니다...{Colors.ENDC}")
        input("\nEnter 키를 누르면 메인 메뉴로 돌아갑니다...")
        return None
    return image_dir


def _restore_original_backups(image_dir: Path) -> bool:
    """기존 백업 파일이 있으면 원본으로 복원"""
    print("--- [단계 -1] 기존 백업 파일 확인 ---")
    original_files = {
        "vbmeta": image_dir / "vbmeta.img.original",
        "vbmeta_system": image_dir / "vbmeta_system.img.original",
        "vendor_boot": image_dir / "vendor_boot.img.original",
        "boot": image_dir / "boot.img.original"
    }
    
    target_img_files = {
        "vbmeta": image_dir / "vbmeta.img",
        "vbmeta_system": image_dir / "vbmeta_system.img",
        "vendor_boot": image_dir / "vendor_boot.img",
        "boot": image_dir / "boot.img"
    }
    
    if all(f.exists() for f in original_files.values()):
        print(f"  > {Colors.OKCYAN}기존 '.original' 백업 파일 4개를 모두 발견했습니다.{Colors.ENDC}")
        print(f"  > {Colors.OKCYAN}원본 이미지로 복원 후 패치를 다시 시작합니다...{Colors.ENDC}")
        try:
            for key in original_files.keys():
                img_path = target_img_files[key]
                orig_path = original_files[key]
                if img_path.exists():
                    img_path.unlink()
                orig_path.rename(img_path)
            print(f"  > {Colors.OKGREEN}원본 이미지 복원 완료.{Colors.ENDC}\n")
        except Exception as restore_e:
            global_end_progress()
            print(f"\n{Colors.FAIL}[오류] 원본 이미지 복원 중 오류 발생: {restore_e}{Colors.ENDC}", file=sys.stderr)
            show_popup("STEP 3 오류 - NG", f"원본 이미지 복원 중 오류 발생:\n{restore_e}",
                      exit_on_close=False, icon=UIConstants.ICON_ERROR)
            print(f"\n{Colors.OKCYAN}메인 메뉴로 돌아갑니다...{Colors.ENDC}")
            input("\nEnter 키를 누르면 메인 메뉴로 돌아갑니다...")
            return False
    else:
        print("  > 기존 백업 파일이 없거나, 일부만 존재합니다. 새로 패치를 시작합니다.\n")
    
    return True


def _backup_images(image_dir: Path, perform_root_patch: bool, rb_indices: Optional[Dict[str, str]]) -> bool:
    """원본 이미지 백업 및 검증"""
    images_to_backup = {
        "vendor_boot.img": image_dir / "vendor_boot.img",
        "vbmeta.img": image_dir / "vbmeta.img",
        "boot.img": image_dir / "boot.img",
        "vbmeta_system.img": image_dir / "vbmeta_system.img"
    }
    
    print(f"  원본 이미지 백업 중...")
    
    missing_images = [name for name, path in images_to_backup.items() if not path.exists()]
    if missing_images:
        global_end_progress()
        missing_list = '\n'.join([f"  - {img}" for img in missing_images])
        print(f"\n{Colors.FAIL}[!] 오류: 해당 이미지 파일이 없습니다:{Colors.ENDC}", file=sys.stderr)
        print(missing_list, file=sys.stderr)
        show_popup(
            "STEP 3 오류 - NG",
            f"해당 이미지 파일이 없습니다:\n\n{chr(10).join(missing_images)}\n\n"
            f"'image' 폴더에 4개의 이미지가 모두 있어야 합니다.\n원본 롬파일인지 확인하십시오.",
            exit_on_close=False,
            icon=UIConstants.ICON_ERROR
        )
        print(f"\n{Colors.OKCYAN}메인 메뉴로 돌아갑니다...{Colors.ENDC}")
        input("\nEnter 키를 누르면 메인 메뉴로 돌아갑니다...")
        return False
    
    has_critical_error = False
    
    for name, path in images_to_backup.items():
        if path.exists():
            bak_path = path.with_suffix(".img.original")
            if bak_path.exists():
                bak_path.unlink()
            shutil.copy2(path, bak_path)
        else:
            if name == "boot.img" and perform_root_patch:
                sys.stderr.write(f"\n{Colors.WARNING}  [경고] 루팅이 요청되었으나 'boot.img'가 없습니다!{Colors.ENDC}")
                has_critical_error = True
            if name == "vbmeta_system.img" and rb_indices and 'vbmeta_system' in rb_indices:
                sys.stderr.write(f"\n{Colors.WARNING}  [경고] 롤백 수정이 요청되었으나 'vbmeta_system.img'가 없습니다!{Colors.ENDC}")
                has_critical_error = True
    
    sys.stdout.flush()
    sys.stderr.flush()
    
    if has_critical_error:
        global_end_progress()
        print(f"\n{Colors.FAIL}[!] 필수 파일이 누락되어 요청된 작업을 완료할 수 없습니다. 중단합니다.{Colors.ENDC}", file=sys.stderr)
        show_popup("STEP 3 오류 - NG",
                  "필수 파일(boot.img 또는 vbmeta_system.img)이 누락되어\n요청된 작업을 완료할 수 없습니다.",
                  exit_on_close=False, icon=UIConstants.ICON_ERROR)
        print(f"\n{Colors.OKCYAN}메인 메뉴로 돌아갑니다...{Colors.ENDC}")
        input("\nEnter 키를 누르면 메인 메뉴로 돌아갑니다...")
        return False
    
    return True


def _patch_vendor_boot_and_vbmeta(image_dir: Path, current_step: int, total_steps: int) -> int:
    """vendor_boot 패치 및 vbmeta 재생성"""
    from core.logger import info, log_patch
    
    vb_bak_path = image_dir / "vendor_boot.img.original"
    vm_bak_path = image_dir / "vbmeta.img.original"
    vb_path = image_dir / "vendor_boot.img"
    vm_path = image_dir / "vbmeta.img"
    vb_patched_temp_path = image_dir / "vendor_boot.img.patched"
    
    info("vendor_boot & vbmeta 패치 시작", image_dir=str(image_dir))
    
    current_step += 1
    print(f"  [{current_step}/{total_steps}] vendor_boot 리전 코드 수정 중...")
    patch_result = patch_region_identifiers(vb_bak_path, vb_patched_temp_path)
    log_patch("vendor_boot 리전 코드 수정", str(vb_bak_path), patch_result, "CN → KR 변환")
    if not patch_result:
        raise RuntimeError("vendor_boot 리전 코드 패치에 실패했습니다.")
    
    current_step += 1
    print(f"  [{current_step}/{total_steps}] 수정된 vendor_boot 이미지 서명 중...")
    sign_result = sign_image_with_footer(vb_patched_temp_path, vb_bak_path, override_rollback_index=None)
    log_patch("vendor_boot AVB 서명", str(vb_patched_temp_path), sign_result, "서명 추가")
    if not sign_result:
        raise RuntimeError("수정된 vendor_boot 서명 실패")
    shutil.move(vb_patched_temp_path, vb_path)
    info("vendor_boot 패치 완료", output=str(vb_path))
    
    current_step += 1
    print(f"  [{current_step}/{total_steps}] vbmeta 이미지 재생성 (해시 갱신) 중...")
    vm_info = get_image_avb_details(vm_bak_path)
    required_vm_keys = ['algorithm', 'pubkey_sha1']
    if not vm_info or not all(key in vm_info for key in required_vm_keys):
        global_end_progress()
        print(f"\n  {Colors.FAIL}[오류] '{vm_bak_path.name}' 분석 실패. 재생성에 필요한 정보가 부족합니다.{Colors.ENDC}", file=sys.stderr)
        raise RuntimeError("원본 vbmeta의 AVB 정보 분석에 실패했습니다.")
    key_file_vm = find_signing_key(vm_info['pubkey_sha1'])
    if not key_file_vm:
        raise RuntimeError("vbmeta 서명 키를 찾지 못했습니다.")
    cmd_make_vbmeta = [
        PYTHON_EXE, str(TOOL_DIR / "avbtool.py"), "make_vbmeta_image",
        "--output", str(vm_path), "--key", str(key_file_vm), "--algorithm", vm_info['algorithm'],
        "--padding_size", "8192",
        "--include_descriptors_from_image", str(vm_bak_path),
        "--include_descriptors_from_image", str(vb_path)
    ]
    if not run_external_command(cmd_make_vbmeta, suppress_output=True):
        raise RuntimeError("vbmeta 이미지 재생성에 실패했습니다.")
    
    return current_step



def start_modification(rom_base_directory: str, perform_root_patch: bool,
                       rb_indices: Optional[Dict[str, str]]) -> None:
    """STEP 3 메인 수정 작업 - 리팩토링 버전"""
    print("=" * 60)
    print(f"이미지 수정 작업을 시작합니다.")
    print(f"대상 롬 경로: {rom_base_directory}")
    print("=" * 60)
    
    # 총 단계 수 계산
    total_steps = 4
    if rb_indices:
        if 'vbmeta_system' in rb_indices:
            total_steps += 1
        if 'boot' in rb_indices and not perform_root_patch:
            total_steps += 1
    if perform_root_patch:
        total_steps += 7
    
    current_step = 0
    
    # image 디렉토리 확인
    image_dir = _check_image_directory(rom_base_directory)
    if not image_dir:
        return None, None
    
    update_sub_task(2, 'in_progress')
    global_print_progress(3, 5, "STEP 3")
    
    # 기존 백업 파일 복원
    if not _restore_original_backups(image_dir):
        return None, None
    
    update_sub_task(2, 'done')
    global_print_progress(3, 5, "STEP 3")
    
    # 원본 이미지 백업
    current_step += 1
    update_sub_task(3, 'in_progress')
    global_print_progress(4, 5, "STEP 3")
    print(f"  [{current_step}/{total_steps}] 원본 이미지 백업 중...")
    
    if not _backup_images(image_dir, perform_root_patch, rb_indices):
        return None, None
    
    try:
        # vendor_boot 및 vbmeta 패치
        current_step = _patch_vendor_boot_and_vbmeta(image_dir, current_step, total_steps)
        
        # 롤백 인덱스 적용
        if rb_indices:
            current_step = apply_rollback_indices(image_dir, rb_indices, perform_root_patch, current_step, total_steps)
        
        # 부트 패칭 (루팅)
        if perform_root_patch:
            new_step = perform_boot_patching(image_dir, rb_indices, current_step, total_steps)
            if new_step == -1:
                print(f"\n{Colors.WARNING}[경고] 부트 이미지 패치에 실패했습니다. (boot.img는 원본으로 유지됩니다){Colors.ENDC}", file=sys.stderr)
                if (image_dir / "boot.img.original").exists():
                    shutil.move(image_dir / "boot.img.original", image_dir / "boot.img")
                current_step += 7
            else:
                current_step = new_step
    
    except Exception as e:
        global_end_progress()
        print(f"\n{Colors.FAIL}{'!' * 60}{Colors.ENDC}")
        print(f"{Colors.FAIL}[!!!] 치명적인 오류 발생: {e}{Colors.ENDC}")
        
        print(f"{Colors.WARNING}오류가 발생하여 원본 이미지로 복구를 시도합니다...{Colors.ENDC}")
        try:
            files_to_restore = {
                "vbmeta.img": image_dir / "vbmeta.img.original",
                "vbmeta_system.img": image_dir / "vbmeta_system.img.original",
                "vendor_boot.img": image_dir / "vendor_boot.img.original",
                "boot.img": image_dir / "boot.img.original"
            }
            restored_count = 0
            for img_name, orig_path in files_to_restore.items():
                img_path = image_dir / img_name
                if img_path.exists():
                    img_path.unlink()
                if orig_path.exists():
                    orig_path.rename(img_path)
                    restored_count += 1
            if restored_count > 0:
                print(f"{Colors.OKGREEN}총 {restored_count}개의 파일을 원본으로 복구했습니다.{Colors.ENDC}")
            else:
                print(f"{Colors.WARNING}복구할 .original 백업 파일이 없습니다.{Colors.ENDC}")
        except Exception as restore_e:
            print(f"{Colors.FAIL}[!!!] 원본 복구 중 추가 오류 발생: {restore_e}{Colors.ENDC}", file=sys.stderr)
        
        print(f"{Colors.FAIL}[!] 작업이 중단되었습니다. 'image' 폴더의 .original 백업 파일로 복구하세요.{Colors.ENDC}")
        print(f"{Colors.FAIL}{'!' * 60}{Colors.ENDC}")
        
        raise Exception(f"STEP 3 패치 실패: {e}") from e
    
    finally:
        if TEMP_WORK_DIR.exists():
            shutil.rmtree(TEMP_WORK_DIR)



# ============================================================================
# China ROM Helper Functions (Shared)
# ============================================================================

def _backup_china_files(image_dir: Path) -> Dict[str, Path]:
    """내수 롬 파일 백업"""
    print(f"{Colors.BOLD}[1/3] 원본 이미지 백업 중...{Colors.ENDC}")
    files_to_restore = {}
    
    vs_path = image_dir / "vbmeta_system.img"
    boot_path = image_dir / "boot.img"
    
    if not vs_path.exists():
        raise FileNotFoundError(f"vbmeta_system.img를 찾을 수 없습니다: {vs_path}")
    if not boot_path.exists():
        raise FileNotFoundError(f"boot.img를 찾을 수 없습니다: {boot_path}")
    
    # vbmeta_system 백업
    vs_orig = vs_path.with_suffix('.img.original')
    if vs_orig.exists():
        vs_orig.unlink()
    shutil.copy2(vs_path, vs_orig)
    files_to_restore['vbmeta_system.img'] = vs_orig
    print(f"  ✓ vbmeta_system.img → vbmeta_system.img.original")
    
    # boot 백업
    boot_orig = boot_path.with_suffix('.img.original')
    if boot_orig.exists():
        boot_orig.unlink()
    shutil.copy2(boot_path, boot_orig)
    files_to_restore['boot.img'] = boot_orig
    print(f"  ✓ boot.img → boot.img.original")
    
    return files_to_restore


def _patch_vbmeta_system_china(image_dir: Path, rb_indices: Optional[Dict[str, str]]) -> None:
    """내수 롬 vbmeta_system 패치"""
    vs_path = image_dir / "vbmeta_system.img"
    vs_orig = image_dir / "vbmeta_system.img.original"
    
    if rb_indices and 'vbmeta_system' in rb_indices:
        print(f"\n{Colors.BOLD}[2/3] vbmeta_system 롤백 인덱스 패치 중...{Colors.ENDC}")
        vm_sys_info = get_image_avb_details(vs_orig)
        required_keys = ['algorithm', 'pubkey_sha1']
        if not vm_sys_info or not all(key in vm_sys_info for key in required_keys):
            raise Exception(f"vbmeta_system.img 분석 실패. 필요한 정보가 없습니다.")
        
        key_file = find_signing_key(vm_sys_info['pubkey_sha1'])
        if not key_file:
            raise Exception("vbmeta_system 서명 키를 찾을 수 없습니다.")
        
        cmd_make_vbmeta_sys = [
            PYTHON_EXE, str(TOOL_DIR / "avbtool.py"), "make_vbmeta_image",
            "--output", str(vs_path),
            "--key", str(key_file),
            "--algorithm", vm_sys_info['algorithm'],
            "--rollback_index", rb_indices['vbmeta_system'],
            "--padding_size", "4096",
            "--include_descriptors_from_image", str(vs_orig)
        ]
        if not run_external_command(cmd_make_vbmeta_sys, suppress_output=True):
            raise Exception("vbmeta_system 롤백 인덱스 패치 실패")
        print(f"  {Colors.OKGREEN}✓ vbmeta_system RB={rb_indices['vbmeta_system']} 패치 완료{Colors.ENDC}")
    else:
        print(f"\n{Colors.BOLD}[2/3] vbmeta_system 패치{Colors.ENDC}")
        print(f"  {Colors.OKCYAN}⏭️  롤백 인덱스 패치 불필요{Colors.ENDC}")


def _patch_boot_china(image_dir: Path, perform_root_patch: bool, rb_indices: Optional[Dict[str, str]]) -> None:
    """내수 롬 boot 패치"""
    print(f"\n{Colors.BOLD}[3/3] boot 이미지 패치 중...{Colors.ENDC}")
    
    boot_path = image_dir / "boot.img"
    boot_orig = image_dir / "boot.img.original"
    
    if perform_root_patch:
        print(f"  {Colors.OKCYAN}→ KernelSU 루팅 진행...{Colors.ENDC}")
        result = perform_boot_patching(image_dir, rb_indices, 1, 8)
        if result == -1:
            raise Exception("boot KernelSU 패치 실패")
        print(f"  {Colors.OKGREEN}✓ boot 루팅 완료{Colors.ENDC}")
    else:
        if rb_indices and 'boot' in rb_indices:
            print(f"  {Colors.OKCYAN}→ boot 롤백 인덱스만 패치...{Colors.ENDC}")
            if not sign_image_with_footer(boot_path, boot_orig, override_rollback_index=rb_indices['boot']):
                raise Exception("boot 롤백 인덱스 패치 실패")
            print(f"  {Colors.OKGREEN}✓ boot RB={rb_indices['boot']} 패치 완료{Colors.ENDC}")
        else:
            print(f"  {Colors.OKCYAN}⏭️  boot 패치 건너뛰기{Colors.ENDC}")


def _restore_china_files(image_dir: Path, files_to_restore: Dict[str, Path]) -> None:
    """내수 롬 파일 복구"""
    print(f"\n{Colors.WARNING}원본 파일로 복구를 시도합니다...{Colors.ENDC}")
    try:
        restored_count = 0
        for img_name, orig_path in files_to_restore.items():
            img_path = image_dir / img_name
            if img_path.exists():
                img_path.unlink()
            if orig_path.exists():
                orig_path.rename(img_path)
                restored_count += 1
        if restored_count > 0:
            print(f"{Colors.OKGREEN}총 {restored_count}개의 파일을 원본으로 복구했습니다.{Colors.ENDC}")
        else:
            print(f"{Colors.WARNING}복구할 .original 백업 파일이 없습니다.{Colors.ENDC}")
    except Exception as restore_e:
        print(f"{Colors.FAIL}[!!!] 원본 복구 중 추가 오류 발생: {restore_e}{Colors.ENDC}", file=sys.stderr)


def start_modification_china(rom_base_directory: str, perform_root_patch: bool,
                             rb_indices: Optional[Dict[str, str]] = None) -> None:
    """내수 롬 패치 로직 - 리팩토링 버전"""
    rom_path = Path(rom_base_directory)
    image_dir = rom_path / "image"
    
    if not image_dir.exists():
        raise FileNotFoundError(f"'image' 폴더를 찾을 수 없습니다: {image_dir}")
    
    update_sub_task(2, 'in_progress')
    global_print_progress(3, 5, "STEP 3")
    
    print(f"\n{Colors.BOLD}{'='*60}{Colors.ENDC}")
    print(f"{Colors.BOLD}내수 롬 패치 시작{Colors.ENDC}")
    print(f"{Colors.BOLD}{'='*60}{Colors.ENDC}\n")
    
    files_to_restore = {}
    
    try:
        files_to_restore = _backup_china_files(image_dir)
        
        update_sub_task(2, 'done')
        update_sub_task(3, 'in_progress')
        global_print_progress(4, 5, "STEP 3")
        
        _patch_vbmeta_system_china(image_dir, rb_indices)
        _patch_boot_china(image_dir, perform_root_patch, rb_indices)
        
    except Exception as e:
        print(f"\n{Colors.FAIL}{'!' * 60}{Colors.ENDC}")
        print(f"{Colors.FAIL}[오류] 내수 롬 패치 중 오류 발생: {e}{Colors.ENDC}")
        print(f"{Colors.FAIL}{'!' * 60}{Colors.ENDC}")
        
        _restore_china_files(image_dir, files_to_restore)
        
        print(f"{Colors.FAIL}[!] 작업이 중단되었습니다. 'image' 폴더의 .original 백업 파일로 복구하세요.{Colors.ENDC}")
        print(f"{Colors.FAIL}{'!' * 60}{Colors.ENDC}")
        
        raise Exception(f"내수 롬 패치 실패: {e}") from e
    
    update_sub_task(3, 'done')
    
    print()
    print(f"{Colors.OKGREEN}{'=' * 60}{Colors.ENDC}")
    print(f"{Colors.OKGREEN}🎉 내수 롬 패치가 성공적으로 완료되었습니다!{Colors.ENDC}")
    changed_files = []
    if rb_indices and 'vbmeta_system' in rb_indices:
        changed_files.append("vbmeta_system.img")
    if perform_root_patch or (rb_indices and 'boot' in rb_indices):
        changed_files.append("boot.img")
    print(f"변경된 파일: {Colors.OKGREEN}{', '.join(changed_files) if changed_files else '없음'}{Colors.ENDC}")
    print("원본 백업은 '.original' 확장자로 'image' 폴더에 저장되었습니다.")
    print(f"{Colors.OKGREEN}{'=' * 60}{Colors.ENDC}")
    
    update_sub_task(4, 'done')
    global_print_progress(5, 5, "STEP 3")




# ============================================================================
# STEP 3-Custom: Helper Functions (리팩토링)
# ============================================================================

def _ask_for_rooting_custom(rom_type: str) -> bool:
    """사용자에게 루팅 선택을 요청"""
    print("=" * 60)
    print(f"{Colors.BOLD}이미지 패치 프로그램(STEP 3-Custom)을 시작합니다.{Colors.ENDC}")
    
    # 롬 타입 표시
    if rom_type == 'china':
        print(f"{Colors.WARNING}[내수 롬 모드]{Colors.ENDC}")
        print(f"  - vendor_boot 패치: ⏭️  건너뛰기 (이미 PRC)")
        print(f"  - vbmeta 패치: ⏭️  건너뛰기 (RB=0)")
        print(f"  - vbmeta_system: 조건부 패치 (다운그레이드 시)")
        print(f"  - boot: 패치 (루팅 선택 + RB 조정)")
    else:
        print(f"{Colors.OKGREEN}[글로벌 롬 모드]{Colors.ENDC}")
        print(f"  - vendor_boot 패치: ✅ ROW → PRC")
        print(f"  - vbmeta 패치: ✅ 재서명")
        print(f"  - vbmeta_system: ✅ 재서명")
        print(f"  - boot: ✅ 패치 (루팅 선택 + RB 조정)")
    
    print("=" * 60)
    print(f"\n{Colors.WARNING}boot.img 이미지를 KernelSU로 루팅하시겠습니까?{Colors.ENDC}")
    print(f"  {Colors.OKCYAN}1. 루팅 진행{Colors.ENDC}")
    print(f"  {Colors.OKCYAN}2. 루팅 건너뛰기{Colors.ENDC}\n")
    
    while True:
        choice = input(f"{Colors.WARNING}선택 (1 또는 2): {Colors.ENDC}").strip()
        if choice == '1':
            print(f"{Colors.OKGREEN}→ 루팅을 진행합니다.{Colors.ENDC}")
            return True
        elif choice == '2':
            print(f"{Colors.OKCYAN}→ 루팅을 건너뜁니다.{Colors.ENDC}")
            return False
        else:
            print(f"{Colors.FAIL}잘못된 입력입니다. 1 또는 2를 입력하십시오.{Colors.ENDC}")


def _check_arb_custom(device_indices: Dict[str, str], 
                      rom_indices: Optional[Dict[str, str]]) -> Optional[Dict[str, str]]:
    """ARB 검사 및 패치 인덱스 결정 - None 반환 시 사용자 취소"""
    if device_indices and rom_indices:
        print("--- [정보] 기기/롬파일 롤백 인덱스 비교 (ARB 검사) ---")
        dev_boot_idx = int(device_indices.get('boot', 0))
        dev_vbm_idx = int(device_indices.get('vbmeta_system', 0))
        rom_boot_idx = int(rom_indices.get('boot', 0))
        rom_vbm_idx = int(rom_indices.get('vbmeta_system', 0))
        
        is_boot_rollback = dev_boot_idx > rom_boot_idx
        is_vbm_rollback = dev_vbm_idx > rom_vbm_idx
        
        if is_boot_rollback or is_vbm_rollback:
            print(f"{Colors.FAIL}{'=' * 60}{Colors.ENDC}")
            print(f"{Colors.FAIL}[!!!] 경고: 안티 롤백(ARB) 보호가 감지되었습니다!{Colors.ENDC}")
            print(f"{Colors.WARNING}현재 기기에 기록된 롤백 인덱스가 설치할 롬파일의 인덱스보다 높습니다.{Colors.ENDC}")
            print("이것은 '롤백 다운그레이드'에 해당합니다.\n")
            print(f"{Colors.BOLD}--- [ 충돌 항목 ] ---{Colors.ENDC}")
            
            if is_boot_rollback:
                print(f"> {Colors.OKCYAN}Boot:{Colors.ENDC} 기기 인덱스 ({dev_boot_idx}) > 롬 인덱스 ({rom_boot_idx})")
            if is_vbm_rollback:
                print(f"> {Colors.OKCYAN}vbmeta_system:{Colors.ENDC} 기기 인덱스 ({dev_vbm_idx}) > 롬 인덱스 ({rom_vbm_idx})")
            
            print(f"\n{Colors.BOLD}--- [ 중요 참고 사항 ] ---{Colors.ENDC}")
            print("'y'를 선택하면, 기기의 롤백 인덱스 값을 롬파일에 강제로 패치하여 플래싱을 진행합니다.\n")
            print(f"{Colors.FAIL}롬파일을 강제로 패치 할 경우, 다음과 같은 제한이 생깁니다:{Colors.ENDC}\n")
            print(f"{Colors.FAIL}{Colors.BOLD}1. OTA 업데이트 제한{Colors.ENDC}")
            print(f"{Colors.WARNING}현재 기기가 패치할 롬파일보다 롤백인덱스가 높기 때문에,")
            print(f"향후 OTA를 이용한 시스템 업데이트가 제한됩니다.{Colors.ENDC}\n")
            print(f"{Colors.FAIL}{'=' * 60}{Colors.ENDC}")
            
            while True:
                choice = input(
                    f"\n{Colors.WARNING}강제로 롤백 인덱스를 패치하여 "
                    f"플래싱을 진행하시겠습니까? (y/n): {Colors.ENDC}"
                ).strip().lower()
                if choice == 'y':
                    indices_to_patch = {}
                    if is_boot_rollback:
                        indices_to_patch['boot'] = device_indices['boot']
                    if is_vbm_rollback:
                        indices_to_patch['vbmeta_system'] = device_indices['vbmeta_system']
                    print(f"\n{Colors.OKCYAN}사용자 확인: 롤백 인덱스 강제 패치를 진행합니다.{Colors.ENDC}\n")
                    return indices_to_patch
                elif choice == 'n':
                    print(f"\n{Colors.FAIL}롬 패치를 취소합니다.{Colors.ENDC}")
                    print(f"\n{Colors.OKCYAN}메인 메뉴로 돌아갑니다...{Colors.ENDC}")
                    input("\nEnter 키를 누르면 메인 메뉴로 돌아갑니다...")
                    return None
                else:
                    print("! 'y' 또는 'n'만 입력해 주세요.")
        else:
            print(f"  > {Colors.OKGREEN}기기와 롬파일의 롤백 인덱스가 호환됩니다. (롤백 패치 불필요){Colors.ENDC}\n")
            return {}
    
    elif device_indices and not rom_indices:
        print(f"--- [정보] 롬파일 롤백 인덱스 정보를 받지 못했습니다. ---")
        print(f"  > {Colors.OKCYAN}기기 롤백 인덱스 파일(Device_Info) 기준으로 롤백 패치를 진행합니다.{Colors.ENDC}\n")
        return device_indices
    
    else:
        if not device_indices:
            print(f"--- [정보] 기기 롤백 인덱스 정보를 받지 못했습니다. ---")
        print(f"  > {Colors.OKCYAN}롤백 인덱스 패치 단계를 건너뜁니다.{Colors.ENDC}\n")
        return {}



def run_step_3_custom(rom_base_directory: str, rom_type: str, device_indices: Dict[str, str],
                      rom_indices: Optional[Dict[str, str]] = None) -> Optional[Tuple[bool, Dict[str, str]]]:
    """
    STEP 3-Custom: 사용자 지정 롬파일 패치 (롬 타입별 조건부 패치) - 리팩토링 버전
    
    Args:
        rom_base_directory: 롬파일 기본 디렉토리
        rom_type: 'global' 또는 'china'
        device_indices: 기기 롤백 인덱스
        rom_indices: 롬 롤백 인덱스 (옵션)
    
    Returns:
        (루팅 여부, 패치된 롤백 인덱스) 또는 None (사용자 취소 시)
    """
    task_names = ["사용자 입력 확인", "ARB 검사", "백업 파일 확인", "이미지 패치 시작", "패치 완료"]
    init_step_progress(3, 5, task_names)
    
    # Task 0: 사용자 입력 확인 (루팅 선택)
    want_root = _ask_for_rooting_custom(rom_type)
    print()
    update_sub_task(0, 'done')
    global_print_progress(1, 5, "STEP 3")
    
    # Task 1: ARB 검사
    update_sub_task(1, 'in_progress')
    global_print_progress(2, 5, "STEP 3")
    
    indices_to_patch = _check_arb_custom(device_indices, rom_indices)
    if indices_to_patch is None:
        return None  # 사용자 취소
    
    update_sub_task(1, 'done')
    global_print_progress(2, 5, "STEP 3")
    
    try:
        # 내수 롬일 경우 vendor_boot/vbmeta 패치 건너뛰기
        if rom_type == 'china':
            start_modification_china(rom_base_directory, want_root, indices_to_patch)
        else:
            start_modification(rom_base_directory, want_root, indices_to_patch)
        
        global_end_progress()
        print(f"\n{Colors.HEADER}--- [STEP 3-Custom 완료] ---{Colors.ENDC}")
        print(f"  > 롬 타입: {rom_type.upper()}")
        print(f"  > 작업 결과: 루팅={want_root}, 적용된 RB 인덱스={indices_to_patch}")
        return want_root, indices_to_patch
    
    except Exception as e:
        global_end_progress()
        error_msg = f"STEP 3-Custom 실행 중 오류 발생: {e}"
        print(f"\n{Colors.FAIL}[!!!] {error_msg}{Colors.ENDC}")
        
        show_popup("STEP 3-Custom 패치 오류 - NG", error_msg, icon=UIConstants.ICON_ERROR)
        
        raise Exception(f"STEP 3-Custom 실패: {e}") from e
    
    finally:
        if TEMP_WORK_DIR.exists():
            shutil.rmtree(TEMP_WORK_DIR)

# ============================================================================
# STEP 3 Helper Functions
# ============================================================================

def _ask_for_rooting() -> bool:
    """루팅 여부 확인"""
    print(f"\n{Colors.WARNING}boot.img 이미지를 KernelSU로 루팅하시겠습니까?{Colors.ENDC}")
    print(f"  {Colors.OKCYAN}1. 루팅 진행{Colors.ENDC}")
    print(f"  {Colors.OKCYAN}2. 루팅 건너뛰기{Colors.ENDC}\n")
    while True:
        choice = input(f"{Colors.WARNING}선택 (1 또는 2): {Colors.ENDC}").strip()
        if choice == '1':
            print(f"{Colors.OKGREEN}→ 루팅을 진행합니다.{Colors.ENDC}")
            return True
        elif choice == '2':
            print(f"{Colors.OKCYAN}→ 루팅을 건너뜁니다.{Colors.ENDC}")
            return False
        else:
            print(f"{Colors.FAIL}잘못된 입력입니다. 1 또는 2를 입력하십시오.{Colors.ENDC}")


def _check_arb_and_get_patch_indices(device_indices: Dict[str, str], 
                                      rom_indices: Dict[str, str]) -> Optional[Dict[str, str]]:
    """ARB 검사 및 패치 인덱스 결정
    
    Returns:
        패치할 인덱스 딕셔너리 또는 None (사용자 취소)
    """
    if not device_indices or not rom_indices:
        if device_indices and not rom_indices:
            print(f"--- [정보] 롬파일 롤백 인덱스 정보를 받지 못했습니다. ---")
            print(f"  > {Colors.OKCYAN}기기 롤백 인덱스 파일(Device_Info) 기준으로 롤백 패치를 진행합니다.{Colors.ENDC}\n")
            return device_indices
        else:
            if not device_indices:
                print(f"--- [정보] 기기 롤백 인덱스 정보를 받지 못했습니다. ---")
            print(f"  > {Colors.OKCYAN}롤백 인덱스 패치 단계를 건너뜁니다.{Colors.ENDC}\n")
            return {}
    
    print("--- [정보] 기기/롬파일 롤백 인덱스 비교 (ARB 검사) ---")
    dev_boot_idx = int(device_indices.get('boot', 0))
    dev_vbm_idx = int(device_indices.get('vbmeta_system', 0))
    rom_boot_idx = int(rom_indices.get('boot', 0))
    rom_vbm_idx = int(rom_indices.get('vbmeta_system', 0))
    
    is_boot_rollback = dev_boot_idx > rom_boot_idx
    is_vbm_rollback = dev_vbm_idx > rom_vbm_idx
    
    if not (is_boot_rollback or is_vbm_rollback):
        print(f"  > {Colors.OKGREEN}기기와 롬파일의 롤백 인덱스가 호환됩니다. (롤백 패치 불필요){Colors.ENDC}\n")
        return {}
    
    # ARB 경고 표시
    print(f"{Colors.FAIL}{'=' * 60}{Colors.ENDC}")
    print(f"{Colors.FAIL}[!!!] 경고: 안티 롤백(ARB) 보호가 감지되었습니다!{Colors.ENDC}")
    print(f"{Colors.WARNING}현재 기기에 기록된 롤백 인덱스가 설치할 롬파일의 인덱스보다 높습니다.{Colors.ENDC}")
    print("이것은 '롤백 다운그레이드'에 해당합니다.")
    print("\n")
    print(f"{Colors.BOLD}--- [ 충돌 항목 ] ---{Colors.ENDC}")
    
    if is_boot_rollback:
        print(f"> {Colors.OKCYAN}Boot:{Colors.ENDC} 기기 인덱스 ({dev_boot_idx}) > 롬 인덱스 ({rom_boot_idx})")
    if is_vbm_rollback:
        print(f"> {Colors.OKCYAN}vbmeta_system:{Colors.ENDC} 기기 인덱스 ({dev_vbm_idx}) > 롬 인덱스 ({rom_vbm_idx})")
    
    print("\n")
    print(f"{Colors.BOLD}--- [ 중요 참고 사항 ] ---{Colors.ENDC}")
    print("'y'를 선택하면, 기기의 롤백 인덱스 값을 롬파일에 강제로 패치하여 플래싱을 진행합니다.\n")
    print(f"{Colors.FAIL}롬파일을 강제로 패치 할 경우, 다음과 같은 제한이 생깁니다:{Colors.ENDC}\n")
    print(f"{Colors.FAIL}{Colors.BOLD}1. OTA 업데이트 제한{Colors.ENDC}")
    print(f"{Colors.WARNING}현재 기기가 패치할 글로벌롬보다 롤백인덱스가 높기 때문에,{Colors.ENDC}")
    print(f"{Colors.WARNING}향후 OTA를 이용한 시스템 업데이트가 제한됩니다.{Colors.ENDC}\n")
    print(f"{Colors.FAIL}{Colors.BOLD}2. OTA 기능 복구 방법{Colors.ENDC}")
    print(f"{Colors.WARNING}OTA 기능을 복구하려면 기기의 롤백인덱스 버전과 같거나 더 높은 새 롬(ROM)이 출시될 때까지 기다려야 합니다.{Colors.ENDC}")
    print(f"{Colors.WARNING}해당 롬이 출시되면, 반드시 지금과 동일한 수동 플래싱 방법으로 기기를 직접 업그레이드해야 합니다.{Colors.ENDC}")
    print(f"{Colors.FAIL}{'=' * 60}{Colors.ENDC}")
    
    while True:
        choice = input(
            f"\n{Colors.WARNING}강제로 롤백 인덱스를 패치하여 "
            f"글로벌롬 플래싱을 진행하시겠습니까? (y/n): {Colors.ENDC}"
        ).strip().lower()
        if choice == 'y':
            indices_to_patch = {}
            if is_boot_rollback:
                indices_to_patch['boot'] = device_indices['boot']
            if is_vbm_rollback:
                indices_to_patch['vbmeta_system'] = device_indices['vbmeta_system']
            print(f"\n{Colors.OKCYAN}사용자 확인: 롤백 인덱스 강제 패치를 진행합니다.{Colors.ENDC}\n")
            return indices_to_patch
        elif choice == 'n':
            print(f"\n{Colors.FAIL}롬 패치를 취소합니다.{Colors.ENDC}")
            print(f"\n{Colors.OKCYAN}메인 메뉴로 돌아갑니다...{Colors.ENDC}")
            input("\nEnter 키를 누르면 메인 메뉴로 돌아갑니다...")
            return None
        else:
            print("! 'y' 또는 'n'만 입력해 주세요.")


# ============================================================================
# STEP 3 Main Function
# ============================================================================

def run_step_3(rom_base_directory: str, device_indices: Dict[str, str],
               rom_indices: Dict[str, str]) -> Optional[Tuple[bool, Dict[str, str]]]:
    """STEP 3 메인 로직 - 리팩토링 버전"""
    task_names = [
        "사용자 입력 확인",
        "ARB 검사",
        "백업 파일 확인",
        "이미지 패치 시작",
        "패치 완료"
    ]
    init_step_progress(3, 5, task_names)
    
    print("=" * 60)
    print(f"{Colors.BOLD}이미지 패치 프로그램(STEP 3)을 시작합니다.{Colors.ENDC}")
    print("=" * 60)
    
    # Task 0: 루팅 여부 확인
    want_root = _ask_for_rooting()
    print()
    update_sub_task(0, 'done')
    global_print_progress(1, 5, "STEP 3")
    
    # Task 1: ARB 검사
    update_sub_task(1, 'in_progress')
    global_print_progress(2, 5, "STEP 3")
    
    indices_to_patch = _check_arb_and_get_patch_indices(device_indices, rom_indices)
    
    if indices_to_patch is None:
        # 사용자가 ARB 패치를 취소함
        return None
    
    update_sub_task(1, 'done')
    global_print_progress(2, 5, "STEP 3")
    
    try:
        start_modification(rom_base_directory, want_root, indices_to_patch)
        
        global_end_progress()
        print(f"\n{Colors.HEADER}--- [STEP 3 완료] ---{Colors.ENDC}")
        print(f"  > 작업 결과: 루팅={want_root}, 적용된 RB 인덱스={indices_to_patch}")
        return want_root, indices_to_patch
    
    except Exception as e:
        global_end_progress()
        error_msg = f"STEP 3 실행 중 오류 발생: {e}"
        print(f"\n{Colors.FAIL}[!!!] {error_msg}{Colors.ENDC}")
        
        show_popup("STEP 3 패치 오류 - NG", error_msg, icon=UIConstants.ICON_ERROR)
        
        raise Exception(f"STEP 3 실패: {e}") from e
    
    finally:
        if TEMP_WORK_DIR.exists():
            shutil.rmtree(TEMP_WORK_DIR)


def start_modification_china(rom_base_directory: str, perform_root_patch: bool,
                             rb_indices: Optional[Dict[str, str]] = None) -> None:
    """내수 롬 패치 로직 - 리팩토링 버전 (2nd)"""
    rom_path = Path(rom_base_directory)
    image_dir = rom_path / "image"
    
    if not image_dir.exists():
        raise FileNotFoundError(f"'image' 폴더를 찾을 수 없습니다: {image_dir}")
    
    update_sub_task(2, 'in_progress')
    global_print_progress(3, 5, "STEP 3")
    
    print(f"\n{Colors.BOLD}{'='*60}{Colors.ENDC}")
    print(f"{Colors.BOLD}내수 롬 패치 시작{Colors.ENDC}")
    print(f"{Colors.BOLD}{'='*60}{Colors.ENDC}\n")
    
    files_to_restore = {}
    
    try:
        files_to_restore = _backup_china_files(image_dir)
        
        update_sub_task(2, 'done')
        update_sub_task(3, 'in_progress')
        global_print_progress(4, 5, "STEP 3")
        
        _patch_vbmeta_system_china(image_dir, rb_indices)
        _patch_boot_china(image_dir, perform_root_patch, rb_indices)
        
    except Exception as e:
        print(f"\n{Colors.FAIL}{'!' * 60}{Colors.ENDC}")
        print(f"{Colors.FAIL}[오류] 내수 롬 패치 중 오류 발생: {e}{Colors.ENDC}")
        print(f"{Colors.FAIL}{'!' * 60}{Colors.ENDC}")
        
        _restore_china_files(image_dir, files_to_restore)
        
        print(f"{Colors.FAIL}[!] 작업이 중단되었습니다. 'image' 폴더의 .original 백업 파일로 복구하세요.{Colors.ENDC}")
        print(f"{Colors.FAIL}{'!' * 60}{Colors.ENDC}")
        
        raise Exception(f"내수 롬 패치 실패: {e}") from e
    
    update_sub_task(3, 'done')
    
    print()
    print(f"{Colors.OKGREEN}{'=' * 60}{Colors.ENDC}")
    print(f"{Colors.OKGREEN}🎉 내수 롬 패치가 성공적으로 완료되었습니다!{Colors.ENDC}")
    changed_files = []
    if rb_indices and 'vbmeta_system' in rb_indices:
        changed_files.append("vbmeta_system.img")
    if perform_root_patch or (rb_indices and 'boot' in rb_indices):
        changed_files.append("boot.img")
    print(f"변경된 파일: {Colors.OKGREEN}{', '.join(changed_files) if changed_files else '없음'}{Colors.ENDC}")
    print("원본 백업은 '.original' 확장자로 'image' 폴더에 저장되었습니다.")
    print(f"{Colors.OKGREEN}{'=' * 60}{Colors.ENDC}")
    
    update_sub_task(4, 'done')
    global_print_progress(5, 5, "STEP 3")


def run_step_3_custom(rom_base_directory: str, rom_type: str, device_indices: Dict[str, str],
                      rom_indices: Optional[Dict[str, str]] = None) -> Optional[Tuple[bool, Dict[str, str]]]:
    """
    STEP 3-Custom: 사용자 지정 롬파일 패치 (롬 타입별 조건부 패치) - 리팩토링 버전
    
    Args:
        rom_base_directory: 롬파일 기본 디렉토리
        rom_type: 'global' 또는 'china'
        device_indices: 기기 롤백 인덱스
        rom_indices: 롬 롤백 인덱스 (옵션)
    
    Returns:
        (루팅 여부, 패치된 롤백 인덱스) 또는 None (사용자 취소 시)
    """
    task_names = ["사용자 입력 확인", "ARB 검사", "백업 파일 확인", "이미지 패치 시작", "패치 완료"]
    init_step_progress(3, 5, task_names)
    
    # Task 0: 사용자 입력 확인 (루팅 선택)
    want_root = _ask_for_rooting_custom(rom_type)
    print()
    update_sub_task(0, 'done')
    global_print_progress(1, 5, "STEP 3")
    
    # Task 1: ARB 검사
    update_sub_task(1, 'in_progress')
    global_print_progress(2, 5, "STEP 3")
    
    indices_to_patch = _check_arb_custom(device_indices, rom_indices)
    if indices_to_patch is None:
        return None  # 사용자 취소
    
    update_sub_task(1, 'done')
    global_print_progress(2, 5, "STEP 3")
    
    try:
        # 내수 롬일 경우 vendor_boot/vbmeta 패치 건너뛰기
        if rom_type == 'china':
            start_modification_china(rom_base_directory, want_root, indices_to_patch)
        else:
            start_modification(rom_base_directory, want_root, indices_to_patch)
        
        global_end_progress()
        print(f"\n{Colors.HEADER}--- [STEP 3-Custom 완료] ---{Colors.ENDC}")
        print(f"  > 롬 타입: {rom_type.upper()}")
        print(f"  > 작업 결과: 루팅={want_root}, 적용된 RB 인덱스={indices_to_patch}")
        return want_root, indices_to_patch
    
    except Exception as e:
        global_end_progress()
        error_msg = f"STEP 3-Custom 실행 중 오류 발생: {e}"
        print(f"\n{Colors.FAIL}[!!!] {error_msg}{Colors.ENDC}")
        
        show_popup("STEP 3-Custom 패치 오류 - NG", error_msg, icon=UIConstants.ICON_ERROR)
        
        raise Exception(f"STEP 3-Custom 실패: {e}") from e
    
    finally:
        if TEMP_WORK_DIR.exists():
            shutil.rmtree(TEMP_WORK_DIR)
