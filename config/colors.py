"""색상 정의"""
import os
import platform

# Windows에서 ANSI 색상 활성화
if platform.system() == "Windows":
    os.system("")

class Colors:
    """ANSI 색상 코드"""
    HEADER = '\033[94m'  # 밝은 파랑 (보라색→파랑으로 변경 - 가독성 향상)
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

