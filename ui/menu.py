"""메뉴 표시 관련 함수들"""
from config.colors import Colors


def show_custom_rom_step_menu() -> int:
    """
    사용자 지정 롬파일 단독 STEP 선택 메뉴를 표시합니다.
    
    Returns:
        int: 사용자가 선택한 STEP 번호 (0-5 또는 99)
    """
    print(f"\n{Colors.HEADER}{'=' * 60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}       사용자 지정 롬파일 - STEP 선택{Colors.ENDC}")
    print(f"{Colors.HEADER}{'=' * 60}{Colors.ENDC}\n")
    
    print(f"{Colors.OKCYAN}  0. STEP 0: RSA 폴더 확인{Colors.ENDC}")
    print(f"{Colors.OKCYAN}  1. STEP 1: 기기 정보 추출{Colors.ENDC}")
    print(f"{Colors.OKCYAN}  2. STEP 2-Custom: 사용자 지정 롬파일 분석{Colors.ENDC}")
    print(f"{Colors.OKCYAN}  3. STEP 3: 롬파일 패치{Colors.ENDC}")
    print(f"{Colors.OKCYAN}  4. STEP 4: 패치 검증{Colors.ENDC}")
    print(f"{Colors.OKCYAN}  5. STEP 5: RSA 폴더로 이동{Colors.ENDC}")
    print(f"\n{Colors.FAIL}  99. 메인 메뉴로 돌아가기{Colors.ENDC}")
    print(f"\n{Colors.HEADER}{'=' * 60}{Colors.ENDC}")
    
    while True:
        try:
            choice = input(f"\n{Colors.WARNING}실행할 STEP 번호를 입력하십시오: {Colors.ENDC}").strip()
            choice_int = int(choice)
            
            if choice_int in [0, 1, 2, 3, 4, 5, 99]:
                return choice_int
            else:
                print(f"{Colors.FAIL}잘못된 입력입니다. 0~5 또는 99를 입력하십시오.{Colors.ENDC}")
        
        except ValueError:
            print(f"{Colors.FAIL}잘못된 입력입니다. 숫자를 입력하십시오.{Colors.ENDC}")

