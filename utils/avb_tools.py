"""AVB 관련 유틸리티 함수"""
import sys
import subprocess
import re
from pathlib import Path
from typing import Optional, Dict

from config.colors import Colors
from config.paths import TOOL_DIR, KNOWN_SIGNING_KEYS, PYTHON_EXE
from core.progress import global_end_progress


def get_image_avb_details(image_path: Path) -> Optional[Dict]:
    """이미지의 AVB 메타데이터 파싱"""
    cmd_params = [PYTHON_EXE, str(TOOL_DIR / "avbtool.py"), "info_image", "--image", str(image_path)]
    try:
        process = subprocess.run(
            cmd_params, check=True, capture_output=True,
            text=True, encoding='utf-8', errors='ignore'
        )
        output = process.stdout.strip()
        info = {}
        prop_args = []
        patterns = {
            'header_image_size': r"^\s*Image Size:\s*(\d+)\s*bytes",
            'partition_size': r"^(?:Image size|Original image size):\s*(\d+)\s*bytes",
            'name': r"Partition Name:\s*(\S+)",
            'rollback_index': r"Rollback Index:\s*(\d+)",
            'salt': r"Salt:\s*([0-9a-fA-F]+)",
            'algorithm': r"Algorithm:\s*(\S+)",
            'pubkey_sha1': r"Public key \(sha1\):\s*([0-9a-fA-F]+)",
            'vbmeta_offset': r"VBMeta offset:\s+(\d+)",
            'vbmeta_size': r"VBMeta size:\s+(\d+)",
        }
        for key, pattern in patterns.items():
            match = re.search(pattern, output, re.MULTILINE)
            if match:
                info[key] = match.group(1)
        if 'partition_size' not in info and 'header_image_size' in info:
            info['partition_size'] = info['header_image_size']
        for line in output.split('\n'):
            if line.strip().startswith("Prop:"):
                parts = line.split('->')
                key_part = parts[0].split(':')[-1].strip()
                val_part = parts[1].strip()[1:-1]
                info[key_part] = val_part
                prop_args.extend(["--prop", f"{key_part}:{val_part}"])
        info['prop_args'] = prop_args
        return info
    except subprocess.CalledProcessError as e:
        global_end_progress()
        print(f"\n  {Colors.FAIL}[오류] '{image_path.name}'의 AVB 정보 분석 실패.{Colors.ENDC}", file=sys.stderr)
        print(f"{Colors.FAIL}{e.stderr.strip()}{Colors.ENDC}", file=sys.stderr)
        return None


def find_signing_key(pubkey_hash: str) -> Optional[Path]:
    """서명 키 해시로 PEM 파일 찾기"""
    key_file = KNOWN_SIGNING_KEYS.get(pubkey_hash)
    if not key_file:
        global_end_progress()
        print(f"\n  {Colors.FAIL}[오류] 알 수 없는 서명 키 해시입니다: {pubkey_hash}{Colors.ENDC}", file=sys.stderr)
    return key_file

