# -*- coding: utf-8 -*-
# アプリ名: 0. Dayスケジュール
import sys
import os
import traceback
from contextlib import contextmanager
from functools import wraps
import sqlite3
import socket
import csv
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTimeEdit, QListWidget, QDialog,
    QLineEdit, QListWidgetItem, QComboBox, QInputDialog, QMessageBox,
    QTableWidget, QTableWidgetItem, QToolTip
)
from PySide6.QtCore import Qt, QTime, QRect, QTimer, QDateTime
from PySide6.QtGui import QPainter, QColor, QBrush, QPen, QFont

# 定数定義
WINDOW_TITLE = "1日のスケジュール設計"
WINDOW_WIDTH = 1200  # 横幅を広げて24時間を見やすく
WINDOW_HEIGHT = 300
DEFAULT_START_TIME = "08:00"
BAR_HEIGHT = 100
HOUR_WIDTH = 45  # 時間軸の幅を調整
COLORS = [
    "#FF9999", "#99FF99", "#9999FF", "#FFFF99", 
    "#FF99FF", "#99FFFF", "#FFB366", "#B366FF"
]

# ウィンドウ位置情報を保存するファイル名
POSITION_FILE = 'window_app_day_schedule.txt'

# 定数としてホスト名を取得
HOSTNAME = socket.gethostname()

# SQLite関連の定数を追加
DB_NAME = "schedule.db"


# 例外処理関数の定義
def get_except_processing():
    """
    例外のトレースバックを取得し、メッセージボックスで表示する
    """
    t, v, tb = sys.exc_info()
    trace = traceback.format_exception(t, v, tb)
    return trace


def restore_position(root):
    """
    CSVファイルからウィンドウの位置を復元する。
    """
    try:
        if os.path.exists(POSITION_FILE):
            with open(POSITION_FILE, 'r', newline='', encoding='utf_8_sig') as csvfile:
                reader = csv.reader(csvfile)
                for row in reader:
                    if row and row[0] == HOSTNAME:
                        coords = row[1].split(',')
                        if len(coords) == 2:
                            x, y = map(int, coords)
                            root.move(x, y)
                        break
    except Exception as e:
        print(f"ウィンドウ位置の復元中にエラーが発生: {str(e)}")


def save_position(window):
    """
    ウィンドウの位置をCSVファイルに保存する。
    """
    try:
        # 既存のデータを読み込む
        existing_data = []
        if os.path.exists(POSITION_FILE):
            with open(POSITION_FILE, 'r', newline='', encoding='utf_8_sig') as csvfile:
                reader = csv.reader(csvfile)
                existing_data = [row for row in reader if row and row[0] != HOSTNAME]

        # 現在の位置を追加
        pos = window.pos()
        current_position = f"{pos.x()},{pos.y()}"
        existing_data.append([HOSTNAME, current_position])

        # データを保存
        with open(POSITION_FILE, 'w', newline='', encoding='utf_8_sig') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerows(existing_data)
    except Exception as e:
        print(f"ウィンドウ位置の保存中にエラーが発生: {str(e)}")


@contextmanager
def get_db_connection():
    """SQLiteデータベース接続のコンテキストマネージャ"""
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        yield conn
    except sqlite3.Error as e:
        print(f"データベース接続エラー: {e}")
        raise
    finally:
        if conn:
            conn.close()


def db_operation(func):
    """データベース操作用デコレータ"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        with get_db_connection() as conn:
            return func(conn, *args, **kwargs)
    return wrapper


def init_db():
    """データベースの初期化とマイグレーション"""
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        
        # 既存のテーブルの存在確認
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schedules'")
        schedules_exists = c.fetchone() is not None
        
        # プロファイルテーブルの作成
        c.execute('''
            CREATE TABLE IF NOT EXISTS profiles
            (id INTEGER PRIMARY KEY AUTOINCREMENT,
             name TEXT UNIQUE)
        ''')
        
        if schedules_exists:
            # 既存のschedulesテーブルが存在する場合、一時テーブルにデータを退避
            # profile_idカラムも含めて退避するように変更
            c.execute('''CREATE TABLE schedules_backup AS 
                     SELECT id, COALESCE(profile_id, 1) as profile_id, name, start_time, end_time, color 
                     FROM schedules''')
            c.execute('DROP TABLE schedules')
        
        # 新しいschedulesテーブルの作成
        c.execute('''
            CREATE TABLE schedules
            (id INTEGER PRIMARY KEY AUTOINCREMENT,
             profile_id INTEGER DEFAULT 1,
             name TEXT,
             start_time TEXT,
             end_time TEXT,
             color TEXT,
             FOREIGN KEY(profile_id) REFERENCES profiles(id))
        ''')
        
        if schedules_exists:
            # バックアップからデータを復元（profile_idを保持）
            c.execute('''
                INSERT INTO schedules (id, profile_id, name, start_time, end_time, color)
                SELECT id, profile_id, name, start_time, end_time, color FROM schedules_backup
            ''')
            c.execute('DROP TABLE schedules_backup')
        
        # デフォルトプロファイルの作成
        c.execute('INSERT OR IGNORE INTO profiles (id, name) VALUES (1, "デフォルト")')

        # last_profile テーブルを作成し、デフォルト値を設定
        c.execute('''
            CREATE TABLE IF NOT EXISTS last_profile
            (id INTEGER PRIMARY KEY CHECK (id = 1),
             profile_id INTEGER DEFAULT 1)
        ''')
        
        # デフォルト値が存在しない場合は挿入
        c.execute('INSERT OR IGNORE INTO last_profile (id, profile_id) VALUES (1, 1)')
        
        conn.commit()
    except sqlite3.Error as e:
        print(f"データベース初期化エラー: {e}")
        raise
    finally:
        conn.close()


def get_exception_trace():
    """例外のトレースバックを取得"""
    t, v, tb = sys.exc_info()
    trace = traceback.format_exception(t, v, tb)
    return trace


def debug_profile_operation(operation_name):
    """プロファイル操作のデバッグ出力用デコレータ"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            
            # self引数の取得
            self = args[0]
            
            print(f"[DEBUG] プロファイル{operation_name}:")
            print(f"  プロファイルID: {self.current_profile_id}")
            
            # スケジュール操作の場合は詳細情報を出力
            if 'schedule' in func.__name__:
                schedule = result if result else (args[1] if len(args) > 1 else None)
                if schedule:
                    print(f"  スケジュール情報:")
                    print(f"    ID: {schedule.id if hasattr(schedule, 'id') else 'New'}")
                    print(f"    名前: {schedule.name}")
                    print(f"    開始時刻: {schedule.start_time}")
                    print(f"    終了時刻: {schedule.end_time}")
                    print(f"    色: {schedule.color}")
            
            return result
        return wrapper
    return decorator


def get_complementary_color(hex_color):
    """補色を計算する関数"""
    color = QColor(hex_color)
    r, g, b = color.red(), color.green(), color.blue()
    
    # 輝度を計算して文字色を調整
    brightness = (r * 299 + g * 587 + b * 114) / 1000
    if brightness > 128:
        return QColor(0, 0, 0)  # 明るい背景には黒文字
    else:
        return QColor(255, 255, 255)  # 暗い背景には白文字


class Schedule:
    """スケジュール項目を管理するクラス"""
    def __init__(self, name, start_time, end_time, color, id=None, profile_id=1):
        self.id = id
        self.profile_id = profile_id
        self.name = name
        self.start_time = start_time
        self.end_time = end_time
        self.color = color

    def save_to_db(self):
        """スケジュールをデータベースに保存"""
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        if self.id is None:
            c.execute('''
                INSERT INTO schedules (profile_id, name, start_time, end_time, color)
                VALUES (?, ?, ?, ?, ?)
            ''', (self.profile_id, self.name, self.start_time, self.end_time, self.color))
            self.id = c.lastrowid
        else:
            c.execute('''
                UPDATE schedules
                SET profile_id=?, name=?, start_time=?, end_time=?, color=?
                WHERE id=?
            ''', (self.profile_id, self.name, self.start_time, self.end_time, self.color, self.id))
        
        conn.commit()
        conn.close()

    @staticmethod
    def load_all_from_db(profile_id=1):
        """指定されたプロファイルのスケジュールをデータベースから読み込む"""
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('SELECT id, name, start_time, end_time, color FROM schedules WHERE profile_id=?', (profile_id,))
        schedules = []
        for row in c.fetchall():
            schedule = Schedule(row[1], row[2], row[3], row[4], row[0], profile_id)
            schedules.append(schedule)
        conn.close()
        return schedules

    @staticmethod
    def delete_from_db(id):
        """指定されたIDのスケジュールを削除"""
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('DELETE FROM schedules WHERE id=?', (id,))
        conn.commit()
        conn.close()

    @staticmethod
    @db_operation
    def clear_all_from_db(conn):
        """すべてのスケジュールを削除"""
        c = conn.cursor()
        c.execute('DELETE FROM schedules')
        conn.commit()

    def get_minutes(self):
        """開始時刻と終了時刻を分単位で返す"""
        start = QTime.fromString(self.start_time, "HH:mm")
        end = QTime.fromString(self.end_time, "HH:mm")
        start_minutes = start.hour() * 60 + start.minute()
        end_minutes = end.hour() * 60 + end.minute()
        return start_minutes, end_minutes


class Profile:
    """プロファイル管理クラス"""
    def __init__(self, name, id=None):
        self.id = id
        self.name = name

    @db_operation
    def save_to_db(conn, self):
        """スケジュールをデータベースに保存"""
        c = conn.cursor()
        if self.id is None:
            c.execute('''
                INSERT INTO schedules (profile_id, name, start_time, end_time, color)
                VALUES (?, ?, ?, ?, ?)
            ''', (self.profile_id, self.name, self.start_time, self.end_time, self.color))
            self.id = c.lastrowid
        else:
            c.execute('''
                UPDATE schedules
                SET profile_id=?, name=?, start_time=?, end_time=?, color=?
                WHERE id=?
            ''', (self.profile_id, self.name, self.start_time, self.end_time, self.color, self.id))
        conn.commit()

    @staticmethod
    def load_profiles_from_db():
        """すべてのプロファイルをデータベースから読み込む"""
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('SELECT id, name FROM profiles')
        profiles = []
        for row in c.fetchall():
            profile = Profile(row[1], row[0])
            profiles.append(profile)
        conn.close()
        return profiles

    @staticmethod
    @db_operation
    def load_all_from_db(conn, profile_id=1):
        """指定されたプロファイルのスケジュールをデータベースから読み込む"""
        c = conn.cursor()
        c.execute('SELECT id, name, start_time, end_time, color FROM schedules WHERE profile_id=?', (profile_id,))
        return [Schedule(row[1], row[2], row[3], row[4], row[0], profile_id) for row in c.fetchall()]


    @staticmethod
    @db_operation
    def delete_from_db(conn, id):
        """指定されたIDのスケジュールを削除"""
        c = conn.cursor()
        c.execute('DELETE FROM schedules WHERE id=?', (id,))
        conn.commit()


class TimeSelectEdit(QTimeEdit):
    """30分刻みの時刻選択ウィジェット"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDisplayFormat("HH:mm")
        self.setTimeRange(QTime(0, 0), QTime(23, 30))
        
    def stepBy(self, steps):
        """30分刻みでの時刻変更"""
        current_time = self.time()
        minutes = current_time.hour() * 60 + current_time.minute()
        minutes += steps * 30  # 30分刻みで増減
        
        # 24時間の範囲内に収める
        minutes = minutes % (24 * 60)
        if minutes < 0:
            minutes += 24 * 60
            
        new_hour = minutes // 60
        new_minute = (minutes % 60) // 30 * 30
        self.setTime(QTime(new_hour, new_minute))

    def mousePressEvent(self, event):
        """マウスクリックで30分刻みに調整"""
        super().mousePressEvent(event)
        current_time = self.time()
        minutes = current_time.minute() // 30 * 30
        self.setTime(QTime(current_time.hour(), minutes))


class AddScheduleDialog(QDialog):
    """スケジュール追加・編集ダイアログ"""
    def __init__(self, parent=None, schedule=None):
        super().__init__(parent)
        self.setWindowTitle("スケジュール追加" if schedule is None else "スケジュール編集")
        layout = QVBoxLayout()
        
        # フォーム部分を横並びに
        form_layout = QHBoxLayout()
        
        # 左側のレイアウト
        left_layout = QVBoxLayout()
        
        # プロファイル選択を追加
        profile_layout = QHBoxLayout()
        profile_layout.addWidget(QLabel("プロファイル:"))
        self.profile_combo = QComboBox()
        self.load_profiles()  # プロファイル一覧を読み込む
        profile_layout.addWidget(self.profile_combo)
        left_layout.addLayout(profile_layout)
        
        # 名前入力
        self.name_edit = QLineEdit()
        left_layout.addWidget(QLabel("予定名:"))
        left_layout.addWidget(self.name_edit)
        
        # 色選択ボタン
        self.color = COLORS[0]
        self.color_button = QPushButton("色を選択")
        self.color_button.clicked.connect(self.choose_color)
        left_layout.addWidget(self.color_button)
        
        form_layout.addLayout(left_layout)
        
        # 右側のレイアウト（時間設定）
        right_layout = QVBoxLayout()
        
        # 開始時刻（30分刻み）
        self.start_time_edit = TimeSelectEdit()
        right_layout.addWidget(QLabel("開始時刻:"))
        right_layout.addWidget(self.start_time_edit)
        
        # 終了時刻（30分刻み）
        self.end_time_edit = TimeSelectEdit()
        right_layout.addWidget(QLabel("終了時刻:"))
        right_layout.addWidget(self.end_time_edit)
        
        form_layout.addLayout(right_layout)
        layout.addLayout(form_layout)
        
        # ボタンレイアウト
        button_layout = QHBoxLayout()
        
        # 確定ボタン
        confirm_button = QPushButton("保存")
        confirm_button.clicked.connect(self.accept)
        button_layout.addWidget(confirm_button)
        
        # 編集モードの場合は削除ボタンを追加
        if schedule is not None:
            delete_button = QPushButton("削除")
            delete_button.clicked.connect(self.delete_schedule)
            button_layout.addWidget(delete_button)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
        
        # 既存のスケジュールデータがある場合は設定
        if schedule is not None:
            self.schedule = schedule
            self.name_edit.setText(schedule.name)
            self.start_time_edit.setTime(QTime.fromString(schedule.start_time, "HH:mm"))
            self.end_time_edit.setTime(QTime.fromString(schedule.end_time, "HH:mm"))
            self.color = schedule.color
            self.color_button.setStyleSheet(f"background-color: {self.color}")
            
            # プロファイルを選択
            index = self.profile_combo.findData(schedule.profile_id)
            if index >= 0:
                self.profile_combo.setCurrentIndex(index)

    def load_profiles(self):
        """プロファイル一覧をコンボボックスに読み込む"""
        self.profile_combo.clear()
        profiles = Profile.load_profiles_from_db()
        for profile in profiles:
            self.profile_combo.addItem(profile.name, profile.id)

    def delete_schedule(self):
        """スケジュールを削除して閉じる"""
        self.done(2)  # 削除用の特別な戻り値

    def choose_color(self):
        """カラーパレットを表示して色を選択"""
        from PySide6.QtWidgets import QColorDialog

        # 現在の色をQColorオブジェクトに変換
        current_color = QColor(self.color)
        
        # カラーダイアログを表示
        color = QColorDialog.getColor(
            initial=current_color,
            parent=self,
            title="色を選択",
            options=QColorDialog.ShowAlphaChannel
        )
        
        # 有効な色が選択された場合、その色を設定
        if color.isValid():
            self.color = color.name().upper()  # HEX形式の色コード (#RRGGBB)
            self.color_button.setStyleSheet(f"background-color: {self.color}")

    def get_schedule_data(self):
        """ダイアログのデータを辞書形式で返す"""
        return {
            'name': self.name_edit.text(),
            'start_time': self.start_time_edit.time().toString("HH:mm"),
            'end_time': self.end_time_edit.time().toString("HH:mm"),
            'color': self.color,
            'profile_id': self.profile_combo.currentData()
        }


class ScheduleListItem(QWidget):
    """スケジュール一覧の項目ウィジェット"""
    def __init__(self, schedule, parent=None):
        super().__init__(parent)
        self.schedule = schedule
        self.main_window = parent  # 追加: MainWindowへの参照を保持
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)
        
        # スケジュール情報のラベル
        self.label = QLabel(f"{schedule.name} ({schedule.start_time}-{schedule.end_time})")
        layout.addWidget(self.label)
        
        layout.addStretch()
        
        # 編集ボタン
        edit_button = QPushButton("編集")
        edit_button.setFixedWidth(60)
        edit_button.clicked.connect(self.edit_clicked)
        layout.addWidget(edit_button)
        
        # 削除ボタン
        delete_button = QPushButton("削除")
        delete_button.setFixedWidth(60)
        delete_button.clicked.connect(self.delete_clicked)
        layout.addWidget(delete_button)

    def edit_clicked(self):
        """編集ボタンのクリックハンドラ"""
        self.main_window.edit_schedule(self.schedule)

    def delete_clicked(self):
        """削除ボタンのクリックハンドラ"""
        self.main_window.delete_schedule(self.schedule)


class TimeBarWidget(QWidget):
    """スケジュールバーを描画するウィジェット"""
    def __init__(self, start_time, schedules, parent=None):
        super().__init__(parent)
        self.start_time = start_time
        self.schedules = schedules
        self.status_height = 40
        self.setMinimumHeight(BAR_HEIGHT + 60 + self.status_height)
        self.highlight_time = QTime.fromString(start_time, "HH:mm")
        
        # ツールチップ関連の追加
        self.setMouseTracking(True)  # マウストラッキングを有効化
        self.tooltip_timer = QTimer(self)
        self.tooltip_timer.setSingleShot(True)
        self.tooltip_timer.timeout.connect(self.showScheduleTooltip)
        self.current_schedule = None
        self.tooltip_position = None

    def mouseMoveEvent(self, event):
        """マウス移動時のイベントハンドラ"""
        schedule = self._get_schedule_at_position(event.pos())
        
        if schedule != self.current_schedule:
            self.tooltip_timer.stop()
            QToolTip.hideText()
            
            if schedule:
                self.current_schedule = schedule
                self.tooltip_position = event.globalPos()
                self.tooltip_timer.start(500)  # 500ms後にツールチップを表示
            else:
                self.current_schedule = None
                self.tooltip_position = None

    def leaveEvent(self, event):
        """マウスがウィジェットを離れた時のイベントハンドラ"""
        self.tooltip_timer.stop()
        QToolTip.hideText()
        self.current_schedule = None
        self.tooltip_position = None

    def showScheduleTooltip(self):
        """スケジュールのツールチップを表示"""
        if self.current_schedule and self.tooltip_position:
            is_current, elapsed_minutes, remaining_minutes = self._get_time_info(self.current_schedule)
            
            tooltip_text = (
                f"予定名: {self.current_schedule.name}\n"
                f"時間: {self.current_schedule.start_time} - {self.current_schedule.end_time}"
            )
            
            if is_current:
                elapsed_str = self._format_time(elapsed_minutes)
                remaining_str = self._format_time(remaining_minutes)
                tooltip_text += f"\n経過時間: {elapsed_str}\n残り時間: {remaining_str}"
            
            QToolTip.showText(self.tooltip_position, tooltip_text)

    def _get_schedule_at_position(self, pos):
        """指定された位置にあるスケジュールを取得"""
        if not (40 <= pos.y() <= 40 + BAR_HEIGHT):  # バーの範囲外
            return None
            
        width = self.width()
        base_time = QTime.fromString(self.start_time, "HH:mm")
        base_minutes = base_time.hour() * 60 + base_time.minute()
        
        # クリック位置を時間に変換
        click_minutes = (pos.x() * 24 * 60) // width
        
        for schedule in self.schedules:
            x_start, x_end, crosses_midnight = self._calculate_schedule_position(
                schedule, width, base_minutes
            )
            
            if crosses_midnight:
                # 日をまたぐ場合
                if (0 <= pos.x() <= x_end) or (x_start <= pos.x() <= width):
                    return schedule
            else:
                # 通常の場合
                if x_start <= pos.x() <= x_end:
                    return schedule
        
        return None

    def set_start_time(self, time_str):
        """開始時刻を設定し、その位置をハイライト表示"""
        self.start_time = time_str
        self.highlight_time = QTime.fromString(time_str, "HH:mm")
        self.repaint()

    def _get_time_info(self, schedule):
        """スケジュールの経過時間と残り時間を計算"""
        now = QTime.currentTime()
        start = QTime.fromString(schedule.start_time, "HH:mm")
        end = QTime.fromString(schedule.end_time, "HH:mm")
        
        # 現在時刻がスケジュール時間内かチェック
        is_current = False
        elapsed_minutes = 0
        remaining_minutes = 0
        
        # 日をまたぐケース対応
        if end < start:
            # スケジュールが日をまたぐ場合
            if now >= start or now <= end:
                is_current = True
                if now >= start:
                    elapsed_minutes = start.secsTo(now) // 60
                else:
                    # 日をまたいでからの経過時間
                    elapsed_minutes = (start.secsTo(QTime(23, 59, 59)) + 60 + QTime(0, 0).secsTo(now)) // 60
                
                if now <= end:
                    remaining_minutes = now.secsTo(end) // 60
                else:
                    # 次の日の終了時刻までの残り時間
                    remaining_minutes = (now.secsTo(QTime(23, 59, 59)) + 60 + QTime(0, 0).secsTo(end)) // 60
        else:
            # 通常のケース
            if start <= now <= end:
                is_current = True
                elapsed_minutes = start.secsTo(now) // 60
                remaining_minutes = now.secsTo(end) // 60
        
        return is_current, elapsed_minutes, remaining_minutes

    def _format_time(self, minutes):
        """分を時間と分に変換してフォーマット"""
        hours = minutes // 60
        mins = minutes % 60
        if hours > 0:
            return f"{hours}時間{mins}分"
        return f"{mins}分"

    def paintEvent(self, event):
        """スケジュールバーの描画"""
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.Antialiasing)
            font = QFont()
            font.setPointSize(9)
            painter.setFont(font)
            
            self._draw_time_markers(painter)
            self._draw_bar_background(painter)
            self._draw_schedules(painter)
            self._draw_current_time(painter)
            self._draw_current_status(painter)
        finally:
            painter.end()

    def _draw_time_markers(self, painter):
        """時間目盛りの描画"""
        width = self.width()
        base_time = QTime.fromString(self.start_time, "HH:mm")
        
        for i in range(49):  # 24時間 × 2（30分刻み）+ 1
            minutes = i * 30
            time = base_time.addSecs(minutes * 60)
            if time.hour() >= 24:
                time = time.addSecs(-24 * 3600)
                
            x = (minutes * width) // (24 * 60)
            
            if i % 2 == 0:  # 1時間ごと
                painter.drawLine(x, 30, x, 40)
                painter.drawText(x - 15, 25, time.toString("HH:mm"))
            else:  # 30分ごと
                painter.drawLine(x, 35, x, 40)

    def _draw_bar_background(self, painter):
        """バーの背景描画"""
        background_rect = QRect(0, 40, self.width(), BAR_HEIGHT)
        painter.setBrush(QBrush(QColor("#FFFFFF")))
        painter.setPen(QPen(QColor("#cccccc")))
        painter.drawRect(background_rect)

    def _draw_schedules(self, painter):
        """全スケジュールの描画"""
        width = self.width()
        base_time = QTime.fromString(self.start_time, "HH:mm")
        base_minutes = base_time.hour() * 60 + base_time.minute()
        
        # スケジュールを時間長でソート（長い順）
        sorted_schedules = []
        for schedule in self.schedules:
            start = QTime.fromString(schedule.start_time, "HH:mm")
            end = QTime.fromString(schedule.end_time, "HH:mm")
            start_minutes, end_minutes = schedule.get_minutes()
            duration = end_minutes - start_minutes if end_minutes > start_minutes else (24 * 60 - start_minutes + end_minutes)
            sorted_schedules.append((schedule, duration))
        
        # 長い順にソート
        sorted_schedules.sort(key=lambda x: (-x[1], x[0].start_time))
        
        # まず長いスケジュールを描画
        for i, (schedule1, duration1) in enumerate(sorted_schedules):
            # 他のスケジュールとの重なりをチェック
            is_overlapped = False
            for schedule2, duration2 in sorted_schedules[:i]:  # 自分より前（長い）スケジュールとチェック
                if self._check_overlap(schedule1, schedule2):
                    is_overlapped = True
                    break
            
            x_start, x_end, crosses_midnight = self._calculate_schedule_position(
                schedule1, width, base_minutes
            )
            
            # 重なっている場合は下部に配置
            y_pos = 40 + (BAR_HEIGHT // 2 if is_overlapped else 0)
            height = BAR_HEIGHT // 2 if is_overlapped else BAR_HEIGHT
            
            if crosses_midnight:
                self._draw_schedule_rect(
                    painter,
                    QRect(x_start, y_pos, width - x_start, height),
                    schedule1,
                    is_overlapped
                )
                self._draw_schedule_rect(
                    painter,
                    QRect(0, y_pos, x_end, height),
                    schedule1,
                    is_overlapped
                )
            else:
                self._draw_schedule_rect(
                    painter,
                    QRect(x_start, y_pos, x_end - x_start, height),
                    schedule1,
                    is_overlapped
                )

    def _check_overlap(self, schedule1, schedule2):
        """2つのスケジュール間の重なりをチェック（5分以上の重なりがある場合にTrue）"""
        start1_minutes, end1_minutes = schedule1.get_minutes()
        start2_minutes, end2_minutes = schedule2.get_minutes()
        
        # 日をまたぐ場合の調整
        if end1_minutes < start1_minutes:
            end1_minutes += 24 * 60
        if end2_minutes < start2_minutes:
            end2_minutes += 24 * 60
        
        # 重なりの判定
        overlap_start = max(start1_minutes, start2_minutes)
        overlap_end = min(end1_minutes, end2_minutes)
        
        return overlap_end - overlap_start >= 5

    def _draw_schedule_rect(self, painter, rect, schedule, is_overlapped):
        """個別のスケジュール矩形の描画"""
        # 境界線の幅を1ピクセル確保
        adjusted_rect = rect.adjusted(1, 1, -1, -1)
        
        # 重なっている場合は半透明に
        color = QColor(schedule.color)
        if is_overlapped:
            color.setAlpha(200)  # 透明度を設定
        painter.setBrush(QBrush(color))
        painter.setPen(QPen(QColor("#666666")))
        painter.drawRect(adjusted_rect)
        
        # テキストの描画
        text_color = get_complementary_color(schedule.color)
        painter.setPen(QPen(text_color))
        
        # 経過時間と残り時間の計算
        is_current, elapsed_minutes, remaining_minutes = self._get_time_info(schedule)
        
        # テキスト表示位置の調整
        text_rect = adjusted_rect.adjusted(2, 2, -2, -2)
        
        # 領域の幅に応じてテキストの表示方法を変更
        if adjusted_rect.width() >= 150:
            if is_overlapped:
                schedule_text = f"{schedule.name}\n{schedule.start_time}-{schedule.end_time}"
            else:
                schedule_text = f"{schedule.name}\n{schedule.start_time}-{schedule.end_time}"
                if is_current:
                    elapsed_str = self._format_time(elapsed_minutes)
                    remaining_str = self._format_time(remaining_minutes)
                    schedule_text += f"\n経過: {elapsed_str} / 残り: {remaining_str}"
        elif adjusted_rect.width() >= 100:
            schedule_text = f"{schedule.name}\n{schedule.start_time}-{schedule.end_time}"
        elif adjusted_rect.width() >= 45:
            schedule_text = f"{schedule.name}\n{schedule.start_time}"
        else:
            schedule_text = schedule.name
        
        painter.drawText(text_rect, Qt.AlignCenter, schedule_text)

    def _calculate_schedule_position(self, schedule, width, base_minutes):
        """スケジュールの描画位置を計算"""
        start = QTime.fromString(schedule.start_time, "HH:mm")
        end = QTime.fromString(schedule.end_time, "HH:mm")
        
        start_minutes = (start.hour() * 60 + start.minute()) - base_minutes
        end_minutes = (end.hour() * 60 + end.minute()) - base_minutes
        
        # 日をまたぐ場合の調整
        if start_minutes < 0:
            start_minutes += 24 * 60
        if end_minutes < 0:
            end_minutes += 24 * 60
            
        x_start = (start_minutes * width) // (24 * 60)
        x_end = (end_minutes * width) // (24 * 60)
        
        return x_start, x_end, end_minutes < start_minutes

    def _draw_current_time(self, painter):
        """現在時刻の赤線描画"""
        width = self.width()
        base_time = QTime.fromString(self.start_time, "HH:mm")
        base_minutes = base_time.hour() * 60 + base_time.minute()
        
        now = QTime.currentTime()
        now_minutes = now.hour() * 60 + now.minute()
        diff_minutes = now_minutes - base_minutes
        
        if diff_minutes < 0:
            diff_minutes += 24 * 60
        
        now_x = (diff_minutes * width) // (24 * 60)
        painter.setPen(QPen(QColor("#FF0000"), 3))
        painter.drawLine(now_x, 30, now_x, BAR_HEIGHT + 40)

    def _draw_current_status(self, painter):
        """現在のスケジュールの状態表示"""
        now = QTime.currentTime()
        status_y = BAR_HEIGHT + 50  # ステータスセクションのY位置
        
        # ステータス背景の描画
        status_rect = QRect(0, status_y, self.width(), self.status_height)
        painter.setPen(QPen(QColor("#cccccc")))
        painter.setBrush(QBrush(QColor("#f5f5f5")))
        painter.drawRect(status_rect)
        
        # 現在進行中のスケジュールを探す
        current_schedules = []
        for schedule in self.schedules:
            is_current, elapsed_minutes, remaining_minutes = self._get_time_info(schedule)
            if is_current:
                current_schedules.append((schedule, elapsed_minutes, remaining_minutes))
        
        if current_schedules:
            # 複数のスケジュールがある場合は横に並べて表示
            total_width = self.width()
            schedule_width = total_width / len(current_schedules)
            
            for i, (schedule, elapsed, remaining) in enumerate(current_schedules):
                x = i * schedule_width
                
                # スケジュール名と時間情報を同じ行に表示するための矩形
                text_rect = QRect(int(x) + 5, status_y + 5, int(schedule_width) - 10, 20)
                
                # 結合したテキストを作成
                combined_text = f"[ {schedule.name} ]  ⏱ {self._format_time(elapsed)}  ➡  残り {self._format_time(remaining)}"
                
                # テキストを描画
                painter.setFont(QFont("Arial", 10))
                painter.setPen(QPen(QColor("#000000")))
                painter.drawText(text_rect, Qt.AlignCenter, combined_text)
                
                # プログレスバーの描画
                total_duration = elapsed + remaining
                progress = elapsed / total_duration if total_duration > 0 else 0
                
                # プログレスバーの背景
                bar_rect = QRect(int(x) + 10, status_y + 30, int(schedule_width) - 20, 6)
                painter.setBrush(QBrush(QColor("#e0e0e0")))
                painter.setPen(QPen(QColor("#cccccc")))
                painter.drawRect(bar_rect)
                
                # プログレスバーの進捗
                progress_width = int((bar_rect.width()) * progress)
                if progress_width > 0:
                    progress_rect = QRect(bar_rect.x(), bar_rect.y(), 
                                        progress_width, bar_rect.height())
                    painter.setBrush(QBrush(QColor(schedule.color)))
                    painter.setPen(Qt.NoPen)
                    painter.drawRect(progress_rect)
        else:
            # スケジュールが無い場合のメッセージ
            painter.setPen(QPen(QColor("#666666")))
            painter.drawText(status_rect, Qt.AlignCenter, "現在進行中のスケジュールはありません")


class DatabaseViewer(QDialog):
    """データベース内容を表示するダイアログ"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("DB確認")
        self.setModal(True)
        layout = QVBoxLayout(self)

        # テーブルウィジェットを追加
        self.table_widget = QTableWidget()
        layout.addWidget(self.table_widget)

        # データベースの内容を読み込む
        self.load_database_content()

    def load_database_content(self):
        """データベースの内容をテーブルに読み込む"""
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('SELECT * FROM schedules')
        rows = c.fetchall()
        column_names = [description[0] for description in c.description]

        self.table_widget.setRowCount(len(rows))
        self.table_widget.setColumnCount(len(column_names))
        self.table_widget.setHorizontalHeaderLabels(column_names)

        for row_index, row_data in enumerate(rows):
            for column_index, data in enumerate(row_data):
                self.table_widget.setItem(row_index, column_index, QTableWidgetItem(str(data)))

        conn.close()


class MainWindow(QMainWindow):
    """メインウィンドウ"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        
        # 保存されたプロファイルIDを読み込む
        self.current_profile_id = self.load_last_profile_id()
        
        # ウィンドウ位置の復元
        restore_position(self)
        
        # 初期化
        self.schedules = Schedule.load_all_from_db(self.current_profile_id)
        self.start_time = DEFAULT_START_TIME
        
        # メインウィジェットとレイアウトの設定
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        # 基準時刻設定
        time_layout = QHBoxLayout()
        self.start_time_edit = TimeSelectEdit()
        self.start_time_edit.setTime(QTime.fromString(DEFAULT_START_TIME))
        time_layout.addWidget(QLabel("基準時刻:"))
        time_layout.addWidget(self.start_time_edit)
        
        # 更新ボタンを追加
        update_button = QPushButton("更新")
        update_button.clicked.connect(self.update_start_time)
        time_layout.addWidget(update_button)
        
        # 時計表示用のラベルを追加
        self.date_time_label = QLabel()
        self.date_time_label.setStyleSheet("font-size: 14px;")
        self.seconds_label = QLabel()
        self.seconds_label.setStyleSheet("font-size: 10px;")
        time_layout.addWidget(self.date_time_label)
        time_layout.addWidget(self.seconds_label)
        
        # タイムバー
        self.timebar = TimeBarWidget(self.start_time, self.schedules)
        layout.addWidget(self.timebar)
        
        # タイマーの設定
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_clock)
        self.timer.start(1000)  # 1秒ごとに更新
        
        # 初回の時刻表示
        self.update_clock()
        
        time_layout.addStretch()
        layout.addLayout(time_layout)
        
        # スケジュール一覧の作成
        self.schedule_list = QListWidget()
        self.schedule_list.setMaximumHeight(80)
        self.schedule_list.itemDoubleClicked.connect(self.on_item_double_clicked)
        # スケジュール一覧をレイアウトに追加
        layout.addWidget(QLabel("登録済みスケジュール（ダブルクリックで編集メニュー）:"))
        layout.addWidget(self.schedule_list)
        
        # プロファイル選択コンボボックスを追加
        profile_layout = QHBoxLayout()
        self.profile_combo = QComboBox()
        self.profile_combo.currentIndexChanged.connect(self.change_profile)
        profile_layout.addWidget(QLabel("プロファイル:"))
        profile_layout.addWidget(self.profile_combo)
        
        # プロファイル管理ボタン
        manage_profile_button = QPushButton("プロファイル管理")
        manage_profile_button.clicked.connect(self.manage_profiles)
        profile_layout.addWidget(manage_profile_button)

        # DB確認ボタンを追加
        db_view_button = QPushButton("DB確認")
        db_view_button.clicked.connect(self.view_database)
        profile_layout.addWidget(db_view_button)

        # 既存のレイアウトにプロファイル選択を追加
        layout = self.centralWidget().layout()
        layout.insertLayout(0, profile_layout)
        
        # プロファイルコンボボックスを更新
        self.update_profile_combo()
        
        # 初期スケジュール読み込み
        self.schedules = Schedule.load_all_from_db(self.current_profile_id)  # プロファイルIDを指定
        self.update_schedule_list()
        
        # ボタン
        button_layout = QHBoxLayout()
        add_button = QPushButton("スケジュール追加")
        add_button.clicked.connect(self.add_schedule)
        button_layout.addWidget(add_button)
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        # 既存のスケジュールをリストに表示
        self.update_schedule_list()

    def load_last_profile_id(self):
        """最後に使用したプロファイルIDを読み込む"""
        try:
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            
            c.execute('SELECT profile_id FROM last_profile WHERE id = 1')
            result = c.fetchone()
            
            if result:
                profile_id = result[0]
                # プロファイルが実際に存在するか確認
                c.execute('SELECT COUNT(*) FROM profiles WHERE id = ?', (profile_id,))
                if c.fetchone()[0] > 0:
                    return profile_id
            
            # プロファイルが存在しない場合はデフォルトに設定
            c.execute('UPDATE last_profile SET profile_id = 1 WHERE id = 1')
            conn.commit()
            return 1
                
        except sqlite3.Error as e:
            print(f"プロファイルID読み込みエラー: {e}")
            return 1
        finally:
            if conn:
                conn.close()

    @debug_profile_operation("保存")
    def save_last_profile_id(self):
        try:
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute('''
                UPDATE last_profile 
                SET profile_id = ? 
                WHERE id = 1
            ''', (self.current_profile_id,))
            conn.commit()
        except sqlite3.Error as e:
            print(f"プロファイルID保存エラー: {e}")
        finally:
            if conn:
                conn.close()

    def moveEvent(self, event):
        """ウィンドウが移動した時に位置を保存"""
        super().moveEvent(event)
        save_position(self)

    def update_clock(self):
        """時計表示の更新"""
        current = QDateTime.currentDateTime()
        self.date_time_label.setText(
            current.toString("yyyy/MM/dd (ddd) HH:mm")
        )
        self.seconds_label.setText(
            current.toString("ss")
        )

        # TimeBarWidgetを更新
        self.timebar.update()

    def on_item_double_clicked(self, item):
        """リストアイテムのダブルクリックハンドラ"""
        schedule = self.schedules[self.schedule_list.row(item)]
        self.edit_schedule(schedule)

    def update_start_time(self):
        """基準時刻の更新"""
        self.start_time = self.start_time_edit.time().toString("HH:mm")
        # 現在のプロファイルIDでスケジュールを読み込むように修正
        self.schedules = Schedule.load_all_from_db(self.current_profile_id)
        # タイムバーのスケジュールを更新
        self.timebar.schedules = self.schedules
        # 基準時刻を設定して再描画
        self.timebar.set_start_time(self.start_time)
        # スケジュール一覧も更新
        self.update_schedule_list()

    def update_profile_combo(self):
        """プロファイル選択コンボボックスを更新"""
        self.profile_combo.clear()
        self.profiles = Profile.load_profiles_from_db()
        for profile in self.profiles:
            self.profile_combo.addItem(profile.name, profile.id)
        # 現在のプロファイルを選択
        index = self.profile_combo.findData(self.current_profile_id)
        if index >= 0:
            self.profile_combo.setCurrentIndex(index)
            # プロファイル変更を保存
            self.save_last_profile_id()
    
    @debug_profile_operation("変更")
    def change_profile(self, index):
        """プロファイル変更時の処理"""
        if index >= 0:
            self.current_profile_id = self.profile_combo.itemData(index)
            # プロファイル変更を即座に保存
            self.save_last_profile_id()
            # 選択されたプロファイルのスケジュールを読み込む
            self.schedules = Schedule.load_all_from_db(self.current_profile_id)
            self.update_schedule_list()
            self.timebar.schedules = self.schedules
            self.timebar.update()

    def closeEvent(self, event):
        """ウィンドウを閉じる際の処理"""
        # 最後に使用したプロファイルIDを保存
        self.save_last_profile_id()
        event.accept()

    def manage_profiles(self):
        """プロファイル管理ダイアログを表示"""
        dialog = ProfileManageDialog(self)
        if dialog.exec():
            self.update_profile_combo()

    @debug_profile_operation("スケジュール追加")
    def add_schedule(self):
        dialog = AddScheduleDialog(self)
        if dialog.exec():
            data = dialog.get_schedule_data()
            schedule = Schedule(
                data['name'],
                data['start_time'],
                data['end_time'],
                data['color'],
                profile_id=self.current_profile_id
            )
            schedule.save_to_db()
            self.schedules = Schedule.load_all_from_db(self.current_profile_id)
            self.update_schedule_list()
            self.timebar.schedules = self.schedules
            self.timebar.update()
            return schedule

    def delete_schedule(self, schedule):
        """スケジュールの削除"""
        # scheduleがQListWidgetItemの場合はScheduleオブジェクトを取得
        if isinstance(schedule, QListWidgetItem):
            schedule = self.schedules[self.schedule_list.row(schedule)]
        
        # 確認ダイアログを表示
        from PySide6.QtWidgets import QMessageBox
        confirm = QMessageBox()
        confirm.setIcon(QMessageBox.Question)
        confirm.setWindowTitle("削除の確認")
        confirm.setText(f"{schedule.name}を本当に削除しますか？")
        confirm.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        confirm.setDefaultButton(QMessageBox.No)
        
        if confirm.exec() == QMessageBox.Yes:
            Schedule.delete_from_db(schedule.id)
            self.schedules.remove(schedule)
            self.update_schedule_list()
            self.timebar.schedules = self.schedules
            self.timebar.update()

    def update_schedule_list(self):
        """スケジュール一覧の更新"""
        self.schedule_list.clear()
        for schedule in self.schedules:
            item = QListWidgetItem(self.schedule_list)
            widget = ScheduleListItem(schedule, self)
            item.setSizeHint(widget.sizeHint())
            self.schedule_list.setItemWidget(item, widget)

    @debug_profile_operation("スケジュール編集")
    def edit_schedule(self, schedule):
        """スケジュールの編集"""
        dialog = AddScheduleDialog(self, schedule)
        result = dialog.exec()
        
        if result == 1:  # OK
            # 変更前の情報を保存
            old_name = schedule.name
            old_start = schedule.start_time
            old_end = schedule.end_time
            old_color = schedule.color
            old_profile = schedule.profile_id
            
            data = dialog.get_schedule_data()
            schedule.name = data['name']
            schedule.start_time = data['start_time']
            schedule.end_time = data['end_time']
            schedule.color = data['color']
            schedule.profile_id = data['profile_id']
            schedule.save_to_db()
            
            # プロファイルが変更された場合は現在のリストから削除
            if old_profile == self.current_profile_id and schedule.profile_id != self.current_profile_id:
                self.schedules.remove(schedule)
            
            # 現在表示中のプロファイルのスケジュールのみを再読み込み
            self.schedules = Schedule.load_all_from_db(self.current_profile_id)
            self.update_schedule_list()
            self.timebar.schedules = self.schedules
            self.timebar.update()
        elif result == 2:  # 削除
            self.delete_schedule(schedule)

    def view_database(self):
        """データベース内容を表示するダイアログを開く"""
        dialog = DatabaseViewer(self)
        dialog.exec()


class ProfileManageDialog(QDialog):
    """プロファイル管理ダイアログ"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("プロファイル管理")
        self.setModal(True)
        
        layout = QVBoxLayout(self)
        
        # プロファイル一覧
        self.profile_list = QListWidget()
        self.update_profile_list()
        layout.addWidget(self.profile_list)
        
        # ボタン
        button_layout = QHBoxLayout()
        
        add_button = QPushButton("追加")
        add_button.clicked.connect(self.add_profile)
        button_layout.addWidget(add_button)
        
        delete_button = QPushButton("削除")
        delete_button.clicked.connect(self.delete_profile)
        button_layout.addWidget(delete_button)
        
        close_button = QPushButton("閉じる")
        close_button.clicked.connect(self.accept)
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)

    def update_profile_list(self):
        """プロファイル一覧を更新"""
        self.profile_list.clear()
        profiles = Profile.load_profiles_from_db()
        for profile in profiles:
            item = QListWidgetItem(f"{profile.name}")
            item.setData(Qt.UserRole, profile.id)
            self.profile_list.addItem(item)

    def add_profile(self):
        """新規プロファイルを追加"""
        name, ok = QInputDialog.getText(self, "プロファイル追加", "プロファイル名:")
        if ok and name:
            profile = Profile(name)
            profile.save_to_db()
            self.update_profile_list()

    def delete_profile(self):
        """選択されたプロファイルを削除"""
        current_item = self.profile_list.currentItem()
        if current_item:
            profile_id = current_item.data(Qt.UserRole)
            if profile_id == 1:
                QMessageBox.warning(self, "エラー", "デフォルトプロファイルは削除できません")
                return
            
            reply = QMessageBox.question(
                self, "確認",
                f"{current_item.text()}を削除してもよろしいですか？",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                Profile.delete_from_db(profile_id)
                self.update_profile_list()


# メイン処理
try:
    # アプリケーション起動前にデータベースを初期化
    init_db()
    
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
except Exception as e:
    trace = get_exception_trace()
    print("エラーが発生しました：", trace)
    sys.exit(1)
