"""
ログ管理システム
バージョン: 1.0.0
特徴:
- アバター処理ログ
- プレセット処理ログ
- パフォーマンスログ
- ログレベル管理
- ログファイル圧縮
- ログ検索機能
"""
import os
import logging
import logging.handlers
import gzip
import shutil
import json
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path
from config_manager import get_config_manager

logger = logging.getLogger(__name__)

class LoggingManager:
    """ログ管理クラス"""
    def __init__(self):
        """初期化"""
        self.config = get_config_manager()
        self.settings = self.config.get_plugin_config("logging_manager")
        
        if self.settings:
            self.log_dir = Path(self.config.config_path).parent / "logs"
            self.log_dir.mkdir(parents=True, exist_ok=True)
            
            self.log_levels = {
                "debug": logging.DEBUG,
                "info": logging.INFO,
                "warning": logging.WARNING,
                "error": logging.ERROR,
                "critical": logging.CRITICAL
            }
            
            self.current_level = self.settings.get("log_level", "info")
            self.max_bytes = self.settings.get("max_bytes", 10485760)  # 10MB
            self.backup_count = self.settings.get("backup_count", 10)
            
            # ログフォーマッターの設定
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            
            # ローテーティングファイルハンドラーの設定
            file_handler = logging.handlers.RotatingFileHandler(
                self.log_dir / "cocoa.log",
                maxBytes=self.max_bytes,
                backupCount=self.backup_count,
                encoding='utf-8'
            )
            file_handler.setFormatter(formatter)
            
            # コンソールハンドラーの設定
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            
            # ルートロガーの設定
            root_logger = logging.getLogger()
            root_logger.setLevel(self.log_levels[self.current_level])
            root_logger.addHandler(file_handler)
            root_logger.addHandler(console_handler)
            
            # ログファイル圧縮スレッドの開始
            self.compression_thread = threading.Thread(target=self._compress_old_logs)
            self.compression_thread.daemon = True
            self.compression_thread.start()
            
            # アバター処理ログの設定
            self.avatar_logger = logging.getLogger("avatar")
            self.avatar_logger.setLevel(logging.INFO)
            
            # プレセット処理ログの設定
            self.preset_logger = logging.getLogger("preset")
            self.preset_logger.setLevel(logging.INFO)
    
    def set_log_level(self, level: str) -> None:
        """ログレベルの設定"""
        if level in self.log_levels:
            self.current_level = level
            root_logger = logging.getLogger()
            root_logger.setLevel(self.log_levels[level])
            logger.info(f"ログレベルを {level} に変更しました")
    
    def _compress_old_logs(self) -> None:
        """古いログファイルの圧縮"""
        while True:
            try:
                # .log.1 以降のファイルを検索
                for file in sorted(self.log_dir.glob("*.log.*")):
                    if not file.suffix.endswith(".gz"):
                        # ファイルを圧縮
                        with open(file, 'rb') as f_in:
                            with gzip.open(f'{file}.gz', 'wb') as f_out:
                                shutil.copyfileobj(f_in, f_out)
                        # 元のファイルを削除
                        file.unlink()
                        logger.info(f"ログファイルを圧縮しました: {file}")
                
                # 30分間隔で実行
                time.sleep(1800)
            except Exception as e:
                logger.error(f"ログファイルの圧縮中にエラーが発生しました: {e}")
                time.sleep(1800)
    
    def log_avatar_processing(self, avatar_id: str, action: str, duration: float) -> None:
        """
        アバター処理のログ記録
        
        Args:
            avatar_id: アバターID
            action: 実行されたアクション
            duration: 処理時間（秒）
        """
        self.avatar_logger.info(
            f"Avatar {avatar_id} - {action} completed in {duration:.3f}s"
        )
    
    def log_preset_processing(self, preset_id: str, action: str, duration: float) -> None:
        """
        プレセット処理のログ記録
        
        Args:
            preset_id: プレセットID
            action: 実行されたアクション
            duration: 処理時間（秒）
        """
        self.preset_logger.info(
            f"Preset {preset_id} - {action} completed in {duration:.3f}s"
        )
    
    def search_logs(self, keyword: str, start_date: str = None, end_date: str = None) -> List[Dict]:
        """
        ログの検索
        
        Args:
            keyword: 検索キーワード
            start_date: 検索開始日時（YYYY-MM-DD HH:MM:SS）
            end_date: 検索終了日時（YYYY-MM-DD HH:MM:SS）
            
        Returns:
            List[Dict]: 検索結果のリスト
        """
        results = []
        try:
            # 日付範囲の設定
            start_dt = datetime.strptime(start_date, "%Y-%m-%d %H:%M:%S") if start_date else None
            end_dt = datetime.strptime(end_date, "%Y-%m-%d %H:%M:%S") if end_date else None
            
            # ログファイルの検索
            for file in sorted(self.log_dir.glob("*.log*")):
                try:
                    # 圧縮ファイルの場合は解凍して検索
                    if file.suffix.endswith(".gz"):
                        with gzip.open(file, 'rt', encoding='utf-8') as f:
                            self._search_file(f, keyword, start_dt, end_dt, results)
                    else:
                        with open(file, 'rt', encoding='utf-8') as f:
                            self._search_file(f, keyword, start_dt, end_dt, results)
                except Exception as e:
                    logger.error(f"ログファイルの検索中にエラーが発生しました: {e}")
            
            return results
        except Exception as e:
            logger.error(f"ログ検索中にエラーが発生しました: {e}")
            return []
    
    def _search_file(self, file_obj, keyword: str, start_dt: datetime, end_dt: datetime, results: List):
        """ファイル内の検索実行"""
        for line in file_obj:
            try:
                # 日時を抽出
                timestamp = line.split(' - ')[0]
                log_dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
                
                # 日付範囲のチェック
                if (start_dt and log_dt < start_dt) or (end_dt and log_dt > end_dt):
                    continue
                
                # キーワード検索
                if keyword.lower() in line.lower():
                    results.append({
                        "timestamp": timestamp,
                        "level": line.split(' - ')[2],
                        "message": line.split(' - ')[3].strip()
                    })
            except Exception:
                continue
    
    def analyze_avatar_performance(self, start_date: str = None, end_date: str = None) -> Dict:
        """
        アバター処理のパフォーマンス分析
        
        Args:
            start_date: 分析開始日時（YYYY-MM-DD HH:MM:SS）
            end_date: 分析終了日時（YYYY-MM-DD HH:MM:SS）
            
        Returns:
            Dict: 分析結果
        """
        analysis = {
            "total_processing": 0,
            "average_duration": 0.0,
            "slowest_processing": None,
            "fastest_processing": None,
            "processing_times": []
        }
        
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d %H:%M:%S") if start_date else None
            end_dt = datetime.strptime(end_date, "%Y-%m-%d %H:%M:%S") if end_date else None
            
            # ログファイルの分析
            for file in sorted(self.log_dir.glob("*.log*")):
                try:
                    # 圧縮ファイルの場合は解凍して分析
                    if file.suffix.endswith(".gz"):
                        with gzip.open(file, 'rt', encoding='utf-8') as f:
                            self._analyze_avatar_file(f, start_dt, end_dt, analysis)
                    else:
                        with open(file, 'rt', encoding='utf-8') as f:
                            self._analyze_avatar_file(f, start_dt, end_dt, analysis)
                except Exception as e:
                    logger.error(f"ログファイルの分析中にエラーが発生しました: {e}")
            
            # 平均処理時間の計算
            if analysis["total_processing"] > 0:
                analysis["average_duration"] = sum(analysis["processing_times"]) / len(analysis["processing_times"])
            
            return analysis
        except Exception as e:
            logger.error(f"パフォーマンス分析中にエラーが発生しました: {e}")
            return analysis
    
    def _analyze_avatar_file(self, file_obj, start_dt: datetime, end_dt: datetime, analysis: Dict):
        """ファイル内のアバター処理分析実行"""
        for line in file_obj:
            try:
                # 日時を抽出
                timestamp = line.split(' - ')[0]
                log_dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
                
                # 日付範囲のチェック
                if (start_dt and log_dt < start_dt) or (end_dt and log_dt > end_dt):
                    continue
                
                # アバター処理ログの解析
                if "Avatar" in line:
                    parts = line.split(' - ')
                    duration = float(parts[3].split(' ')[-1].strip('s'))
                    analysis["processing_times"].append(duration)
                    analysis["total_processing"] += 1
                    
                    # 最も遅い処理の更新
                    if analysis["slowest_processing"] is None or duration > analysis["slowest_processing"]:
                        analysis["slowest_processing"] = duration
                    
                    # 最も早い処理の更新
                    if analysis["fastest_processing"] is None or duration < analysis["fastest_processing"]:
                        analysis["fastest_processing"] = duration
            except Exception:
                continue
