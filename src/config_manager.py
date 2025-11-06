"""전역 설정 관리 (전역 변수 대체)"""
import os
from typing import Optional


class AppConfig:
    """애플리케이션 전역 설정 관리 (Singleton)"""
    
    _instance: Optional['AppConfig'] = None
    
    def __new__(cls) -> 'AppConfig':
        """싱글톤 인스턴스 생성"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self) -> None:
        """싱글톤 인스턴스 초기화 (최초 1회만 실행)"""
        if self._initialized:
            return
        
        # 개발자 모드
        self._dev_mode = False
        self._dev_password = "sksmscjswodlqslek"
        
        self._initialized = True
    
    @property
    def dev_mode(self) -> bool:
        """개발자 모드 상태"""
        # 환경 변수도 체크
        env_dev = os.getenv('DEV_MODE', '').lower() in ('true', '1', 'yes')
        return self._dev_mode or env_dev
    
    @dev_mode.setter
    def dev_mode(self, value: bool) -> None:
        """개발자 모드 설정"""
        self._dev_mode = value
    
    def check_dev_password(self, password: str) -> bool:
        """개발자 비밀번호 확인"""
        return password == self._dev_password
    
    def enable_dev_mode(self, password: str) -> bool:
        """개발자 모드 활성화"""
        if self.check_dev_password(password):
            self._dev_mode = True
            return True
        return False
    
    def disable_dev_mode(self) -> None:
        """개발자 모드 비활성화"""
        self._dev_mode = False


# 전역 싱글톤 인스턴스
_app_config = AppConfig()


def get_config() -> AppConfig:
    """앱 설정 인스턴스 반환"""
    return _app_config

