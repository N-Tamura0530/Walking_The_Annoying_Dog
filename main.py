import sys
import random
from pathlib import Path
from PyQt5.QtWidgets import QApplication, QLabel, QWidget, QMessageBox
from PyQt5.QtCore import QTimer, Qt, QPoint, QRect
from PyQt5.QtGui import QPixmap

# --- デスクトップ上を動くペットウィンドウ ---
class DesktopPet(QWidget):

    def __init__(self, image_path):
        """
        クラス初期化メソッド。DesktopPetクラスのインスタンスを作成する際に呼び出される。
        画像パスを受け取り、ウィンドウの初期設定やアニメーションフレームの切り出し、タイマーのセットアップなどを行う。
        """
        # 親クラス(QWidget)の初期化処理を呼び出す
        super().__init__()
        
        # ウィンドウの基本設定その１。フレームなし、常に最前面、ツールウィンドウ、背景透明
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        # ウィンドウの基本設定その２。透明背景を有効にする（画像の非表示部分を透過させる）
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # 画像を載せるQLabelを作成。
        self.label = QLabel(self)
        # マウスイベントをQLabelが受け取らないようにする（その結果、親ウィジェットがイベントを受け取れ、mousePressEventやmouseMoveEventが機能する）
        self.label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        # 画像を読み込んでQPixmapオブジェクトを作成。これがアニメーションの元画像となる。
        self.original_pixmap = QPixmap(str(image_path))

        # 読み込んだ画像（スプライトシート）から、どの部分を読み込んでアニメーションに使うか指定。まずは通常移動時（方向別）
        self.left_move_frames = [
            self.original_pixmap.copy(0,0,100,100),
            self.original_pixmap.copy(100,0,100,100),
        ]
        self.right_move_frames = [
            self.original_pixmap.copy(200,0,100,100),
            self.original_pixmap.copy(300,0,100,100),
        ]

        # 読み込んだ画像（スプライトシート）から、どの部分を読み込んでアニメーションに使うか指定。次は休止時（方向別）
        self.left_rest_hold = self.original_pixmap.copy(100,100,100,100)
        self.right_rest_hold = self.original_pixmap.copy(200,100,100,100)
        self.left_rest_frames = [
            self.original_pixmap.copy(0,100,100,100),
            self.original_pixmap.copy(0,200,100,100),
        ]
        self.right_rest_frames = [
            self.original_pixmap.copy(300,100,100,100),
            self.original_pixmap.copy(300,200,100,100),
        ]

        self.current_frames = self.right_move_frames
        self.frame_index = 0
        self.pixmap = self.current_frames[self.frame_index]
        self.label.setPixmap(self.pixmap)
        self.resize(self.pixmap.width(), self.pixmap.height())
        self.pos_x = 100
        self.pos_y = 100
        self.move(self.pos_x, self.pos_y)  # 初期位置（左上から100,100）
        self.move_timer = QTimer()
        self.move_timer.timeout.connect(self.update_position)
        self.move_timer.start(30)  # 30msごとに自動移動
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self.update_frame)
        self.animation_timer.start(1000)  # 1秒ごとにコマ切り替え
        self.rest_transition_timer = QTimer(self)
        self.rest_transition_timer.setSingleShot(True)
        self.rest_transition_timer.timeout.connect(self.enter_rest_phase_1)
        self.rest_phase2_timer = QTimer(self)
        self.rest_phase2_timer.setSingleShot(True)
        self.rest_phase2_timer.timeout.connect(self.enter_rest_phase_2)
        self.rest_resume_timer = QTimer(self)
        self.rest_resume_timer.setSingleShot(True)
        self.rest_resume_timer.timeout.connect(self.exit_rest_mode)
        self.speed_x = 2
        self.speed_y = 1
        self.drag_pos = None  # 移動速度・ドラッグ位置
        self.is_resting = False
        self.rest_direction = 1
        self.sync_move_frames_with_direction(reset_index=False)
        self.schedule_next_rest_start()

    def update_position(self):
        """
        ウィンドウを自動で移動させる
        画面端に当たったら反射させる
        primaryScreenから完全に出た場合は初期位置に戻す
        """
        screen_rect = QApplication.primaryScreen().geometry()
        max_x = screen_rect.width() - self.width()
        max_y = screen_rect.height() - self.height()

        # 端で反射する前に、現在位置を画面内へ補正する
        if self.pos_x < 0:
            self.pos_x = 0
            if self.speed_x < 0:
                self.speed_x = -self.speed_x
                self.sync_move_frames_with_direction(reset_index=True)
        elif self.pos_x > max_x:
            self.pos_x = max_x
            if self.speed_x > 0:
                self.speed_x = -self.speed_x
                self.sync_move_frames_with_direction(reset_index=True)

        if self.pos_y < 0:
            self.pos_y = 0
            if self.speed_y < 0:
                self.speed_y = -self.speed_y
        elif self.pos_y > max_y:
            self.pos_y = max_y
            if self.speed_y > 0:
                self.speed_y = -self.speed_y

        # 位置更新
        self.pos_x += self.speed_x
        self.pos_y += self.speed_y
        self.move(self.pos_x, self.pos_y)
        self.apply_current_frame()

        # 完全にprimaryScreen外に出た場合は初期位置に戻す
        pet_rect = QRect(self.pos_x, self.pos_y, self.width(), self.height())
        if not screen_rect.intersects(pet_rect):
            self.pos_x = 100
            self.pos_y = 100
            self.move(self.pos_x, self.pos_y)

    def set_display_pixmap(self, pixmap):
        self.pixmap = pixmap
        self.label.setPixmap(self.pixmap)
        self.resize(self.pixmap.width(), self.pixmap.height())

    def sync_move_frames_with_direction(self, reset_index):
        """
        移動方向に応じて通常移動用フレームセットを選ぶ
        """
        target_frames = self.right_move_frames if self.speed_x > 0 else self.left_move_frames
        if target_frames is not self.current_frames:
            self.current_frames = target_frames
            if reset_index:
                self.frame_index = 0

    def apply_current_frame(self):
        """
        現在のフレームセットの表示コマを反映
        """
        if not self.current_frames:
            return
        current_frame = self.current_frames[self.frame_index]
        self.set_display_pixmap(current_frame)

    def update_frame(self):
        """
        1秒ごとに現在フレームセット内のコマを切り替える
        """
        if not self.current_frames:
            return
        self.frame_index = (self.frame_index + 1) % len(self.current_frames)
        self.apply_current_frame()

    def schedule_next_rest_start(self):
        """
        通常移動中に、30～60秒後の休止開始を予約する
        """
        wait_ms = random.randint(30, 60) * 1000
        self.rest_transition_timer.start(wait_ms)

    def enter_rest_phase_1(self):
        """
        移動を止め、方向別の休止画像を5秒表示する
        """
        self.is_resting = True
        self.rest_direction = 1 if self.speed_x > 0 else -1
        self.move_timer.stop()
        self.current_frames = []
        hold_frame = self.right_rest_hold if self.rest_direction > 0 else self.left_rest_hold
        self.set_display_pixmap(hold_frame)
        self.rest_phase2_timer.start(5000)

    def enter_rest_phase_2(self):
        """
        方向別の休止アニメーションを開始し、30～60秒後に通常移動へ復帰
        """
        self.current_frames = self.right_rest_frames if self.rest_direction > 0 else self.left_rest_frames
        self.frame_index = 0
        self.apply_current_frame()
        wait_ms = random.randint(30, 60) * 1000
        self.rest_resume_timer.start(wait_ms)

    def exit_rest_mode(self):
        """
        通常移動に戻し、次回の休止開始を再予約する
        """
        self.is_resting = False
        self.sync_move_frames_with_direction(reset_index=True)
        self.move_timer.start(30)
        self.apply_current_frame()
        self.schedule_next_rest_start()

    def mousePressEvent(self, event):
        """
        左クリックでドラッグ開始。自動移動を一時停止
        右クリックで終了確認ダイアログ
        """
        if event.button() == Qt.LeftButton:
            self.drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            self.move_timer.stop()
            event.accept()
        elif event.button() == Qt.RightButton:
            reply = QMessageBox.question(self, '終了確認', 'アプリを終了しますか？',
                                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                QApplication.quit()
            event.accept()

    def mouseMoveEvent(self, event):
        """
        ドラッグ中はマウスに追従して移動。内部座標も同期
        """
        if self.drag_pos is not None and event.buttons() & Qt.LeftButton:
            new_pos = event.globalPos() - self.drag_pos
            self.move(new_pos)
            self.pos_x = new_pos.x()
            self.pos_y = new_pos.y()
            event.accept()

    def mouseReleaseEvent(self, event):
        """
        ドラッグ終了時に自動移動を再開
        """
        if event.button() == Qt.LeftButton and self.drag_pos is not None:
            self.drag_pos = None
            if not self.is_resting:
                self.move_timer.start(30)
            event.accept()


if __name__ == '__main__':
    #pyQtアプリを動かすための本体（アプリケーションオフジェクト）を作成
    app = QApplication(sys.argv)
    
    # 画像パスをmain.py基準で取得
    image_path = Path(__file__).resolve().parent / 'Annoying Dog.png'
    if not image_path.exists():
        # 画像ファイルがなければエラー表示して終了
        QMessageBox.critical(None, '画像エラー', f'画像が見つかりません:\n{image_path}')
        sys.exit(1)
    
    # DesktopPetウィンドウを作成
    pet = DesktopPet(image_path)
    if pet.pixmap.isNull():
        # 画像が壊れている場合もエラー表示して終了
        QMessageBox.critical(None, '画像エラー', f'画像を読み込めませんでした:\n{image_path}')
        sys.exit(1)
    
    # ペットウィンドウを表示
    pet.show()
    
    # アプリケーション実行。app.exec_()はイベントループを開始し、終了コードを返す。
    sys.exit(app.exec_())