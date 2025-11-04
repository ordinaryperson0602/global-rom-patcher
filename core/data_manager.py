"""STEP 간 데이터 관리"""
import os
import json
import time
from typing import Optional
from config.colors import Colors
from config.paths import STEP_DATA_FILE, CUSTOM_ROM_STEP_DATA_FILE

def save_step_data(step_number: int, data: dict) -> bool:
    """STEP 실행 결과를 JSON 파일로 저장"""
    try:
        # 기존 데이터 로드
        if os.path.exists(STEP_DATA_FILE):
            try:
                with open(STEP_DATA_FILE, 'r', encoding='utf-8') as f:
                    all_data = json.load(f)
            except (json.JSONDecodeError, PermissionError):
                all_data = {}
        else:
            all_data = {}
        
        all_data[f"step_{step_number}"] = data
        
        # 임시 파일에 먼저 쓰기
        temp_file = STEP_DATA_FILE + '.tmp'
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2)
        
        # 기존 파일 삭제 시도
        if os.path.exists(STEP_DATA_FILE):
            try:
                os.chmod(STEP_DATA_FILE, 0o666)
                os.remove(STEP_DATA_FILE)
            except PermissionError:
                backup_name = STEP_DATA_FILE + f'.backup_{int(time.time())}'
                try:
                    os.rename(STEP_DATA_FILE, backup_name)
                    print(f"{Colors.WARNING}[경고] 기존 파일을 '{backup_name}'으로 백업했습니다.{Colors.ENDC}")
                except:
                    pass
        
        # 임시 파일을 정식 파일명으로 변경
        os.rename(temp_file, STEP_DATA_FILE)
        
        print(f"{Colors.OKGREEN}[정보] STEP {step_number} 데이터가 저장되었습니다.{Colors.ENDC}")
        return True
    except Exception as e:
        print(f"{Colors.FAIL}[오류] 데이터 저장 실패: {e}{Colors.ENDC}")
        print(f"{Colors.WARNING}[정보] 데이터는 메모리에 유지되며 프로그램은 계속 실행됩니다.{Colors.ENDC}")
        return False

def load_step_data(step_number: int) -> Optional[dict]:
    """저장된 STEP 데이터 로드"""
    try:
        if not os.path.exists(STEP_DATA_FILE):
            return None
        
        with open(STEP_DATA_FILE, 'r', encoding='utf-8') as f:
            all_data = json.load(f)
        
        step_key = f"step_{step_number}"
        if step_key in all_data:
            print(f"{Colors.OKGREEN}[정보] STEP {step_number} 데이터를 로드했습니다.{Colors.ENDC}")
            return all_data[step_key]
        else:
            return None
    except Exception as e:
        print(f"{Colors.FAIL}[오류] 데이터 로드 실패: {e}{Colors.ENDC}")
        return None

def check_step_prerequisites(step_number: int) -> bool:
    """STEP 실행 전 필수 조건 확인"""
    if step_number == 1:
        return True
    
    required_steps = list(range(1, step_number))
    
    for req_step in required_steps:
        data = load_step_data(req_step)
        if not data:
            print(f"{Colors.FAIL}[오류] STEP {req_step}의 데이터가 없습니다.{Colors.ENDC}")
            print(f"{Colors.WARNING}STEP {step_number}을(를) 실행하려면 먼저 STEP {req_step}을(를) 완료해야 합니다.{Colors.ENDC}")
            return False
    
    return True


# ========================================
# Custom ROM용 데이터 관리 함수
# ========================================

def save_custom_rom_step_data(step_number: int, data: dict) -> bool:
    """사용자 지정 롬파일 STEP 데이터 저장"""
    try:
        # 기존 데이터 로드
        if os.path.exists(CUSTOM_ROM_STEP_DATA_FILE):
            try:
                with open(CUSTOM_ROM_STEP_DATA_FILE, 'r', encoding='utf-8') as f:
                    all_data = json.load(f)
            except (json.JSONDecodeError, PermissionError):
                all_data = {}
        else:
            all_data = {}
        
        all_data[f"step_{step_number}"] = data
        
        # 임시 파일에 먼저 쓰기
        temp_file = CUSTOM_ROM_STEP_DATA_FILE + '.tmp'
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2)
        
        # 기존 파일 삭제 시도
        if os.path.exists(CUSTOM_ROM_STEP_DATA_FILE):
            try:
                os.chmod(CUSTOM_ROM_STEP_DATA_FILE, 0o666)
                os.remove(CUSTOM_ROM_STEP_DATA_FILE)
            except PermissionError:
                backup_name = CUSTOM_ROM_STEP_DATA_FILE + f'.backup_{int(time.time())}'
                try:
                    os.rename(CUSTOM_ROM_STEP_DATA_FILE, backup_name)
                    print(f"{Colors.WARNING}[경고] 기존 파일을 '{os.path.basename(backup_name)}'으로 백업했습니다.{Colors.ENDC}")
                except:
                    pass
        
        # 임시 파일을 정식 파일명으로 변경
        os.rename(temp_file, CUSTOM_ROM_STEP_DATA_FILE)
        
        print(f"{Colors.OKGREEN}[정보] Custom ROM STEP {step_number} 데이터가 저장되었습니다.{Colors.ENDC}")
        return True
    except Exception as e:
        print(f"{Colors.FAIL}[오류] 데이터 저장 실패: {e}{Colors.ENDC}")
        print(f"{Colors.WARNING}[정보] 데이터는 메모리에 유지되며 프로그램은 계속 실행됩니다.{Colors.ENDC}")
        return False


def load_custom_rom_step_data(step_number: int) -> Optional[dict]:
    """저장된 Custom ROM STEP 데이터 로드"""
    try:
        if not os.path.exists(CUSTOM_ROM_STEP_DATA_FILE):
            return None
        
        with open(CUSTOM_ROM_STEP_DATA_FILE, 'r', encoding='utf-8') as f:
            all_data = json.load(f)
        
        step_key = f"step_{step_number}"
        if step_key in all_data:
            print(f"{Colors.OKGREEN}[정보] Custom ROM STEP {step_number} 데이터를 로드했습니다.{Colors.ENDC}")
            return all_data[step_key]
        else:
            return None
    except Exception as e:
        print(f"{Colors.FAIL}[오류] 데이터 로드 실패: {e}{Colors.ENDC}")
        return None

