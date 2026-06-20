import cv2
import time
import pygame
import random
import tkinter as tk
from pathlib import Path
from PIL import Image, ImageTk

# =====================
# 設定
# =====================
BELL_FILE = "bell.mp3"
CHARACTER_IMAGE_FILE = "character.png"

VOICE_DIR = Path("voices")
VOICE_EXTENSIONS = [".mp3", ".wav", ".ogg"]

WELCOME_KEYWORD = "いらっしゃいませ"

CAMERA_WIDTH = 320
CAMERA_HEIGHT = 240
CAMERA_FPS = 15

MIN_AREA = 800

cooldown = 3

# 起動直後の誤検知対策
STARTUP_IGNORE_SECONDS = 5

# 動きが消えてから再検知可能に戻すまで
MOTION_CLEAR_SECONDS = 2

# =====================
# キャラ表示設定
# =====================
# ディスプレイの高さに対して何%まで表示するか
CHARACTER_HEIGHT_RATIO = 0.95

# 上下の安全余白
SCREEN_HEIGHT_MARGIN = 40

# 横幅の最大値。Noneなら高さ基準だけで決める
CHARACTER_MAX_WIDTH = None

# 表示位置
# Noneにすると中央配置
CHARACTER_X = None
CHARACTER_Y = None

# 背景透過に使う色
TRANSPARENT_COLOR = "#ff00ff"

# =====================
# 音声初期化
# =====================
pygame.mixer.init()
pygame.mixer.set_num_channels(8)

bell_sound = pygame.mixer.Sound(BELL_FILE)

voice_files = [
    p for p in VOICE_DIR.iterdir()
    if p.is_file() and p.suffix.lower() in VOICE_EXTENSIONS
]

voice_sounds = []
welcome_sound = None
welcome_file_name = None

for p in voice_files:
    try:
        sound = pygame.mixer.Sound(str(p))

        if WELCOME_KEYWORD in p.name and welcome_sound is None:
            welcome_sound = sound
            welcome_file_name = p.name
        else:
            voice_sounds.append((p.name, sound))

    except Exception as e:
        print(f"音声読み込み失敗: {p.name} / {e}")

if welcome_sound is None:
    print("固定音声『いらっしゃいませ』が見つかりません")
    print("ファイル名に『いらっしゃいませ』を含めてください")

if len(voice_sounds) == 0:
    print("ランダム再生用の音声ファイルがありません")

print(f"固定音声: {welcome_file_name}")
print(f"ランダム音声数: {len(voice_sounds)}")

# =====================
# キャラ表示ウィンドウ初期化
# =====================
root = tk.Tk()
root.withdraw()

character_window = tk.Toplevel(root)
character_window.withdraw()

# タイトルバーを非表示
character_window.overrideredirect(True)

# 最前面に表示
character_window.attributes("-topmost", True)

# 背景透過
character_window.configure(bg=TRANSPARENT_COLOR)

try:
    character_window.attributes("-transparentcolor", TRANSPARENT_COLOR)
except tk.TclError:
    print("この環境では transparentcolor が使えない可能性があります")

character_label = tk.Label(
    character_window,
    bg=TRANSPARENT_COLOR,
    borderwidth=0,
    highlightthickness=0
)
character_label.pack()

character_photo = None


def load_character_image():
    """
    キャラ画像を読み込み、ディスプレイの縦サイズに合わせて、
    縦横比を維持したままリサイズする
    """
    image_path = Path(CHARACTER_IMAGE_FILE)

    if not image_path.exists():
        print(f"キャラ画像が見つかりません: {CHARACTER_IMAGE_FILE}")
        return None, 0, 0

    try:
        img = Image.open(image_path).convert("RGBA")
    except Exception as e:
        print(f"キャラ画像を読み込めません: {e}")
        return None, 0, 0

    original_width, original_height = img.size

    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()

    # ディスプレイ縦サイズから、表示できる最大高さを決める
    max_height_by_screen = int(screen_h * CHARACTER_HEIGHT_RATIO) - SCREEN_HEIGHT_MARGIN

    if max_height_by_screen <= 0:
        max_height_by_screen = screen_h

    # 高さ基準のスケール
    scale_by_height = max_height_by_screen / original_height

    # 横幅制限がある場合だけ横幅基準も使う
    if CHARACTER_MAX_WIDTH is not None:
        scale_by_width = CHARACTER_MAX_WIDTH / original_width
        scale = min(scale_by_height, scale_by_width)
    else:
        scale = scale_by_height

    new_width = int(original_width * scale)
    new_height = int(original_height * scale)

    img = img.resize((new_width, new_height), Image.LANCZOS)

    return ImageTk.PhotoImage(img), new_width, new_height


def show_character():
    """
    キャラ画像を表示する
    """
    global character_photo

    character_photo, img_w, img_h = load_character_image()

    if character_photo is None:
        return

    character_label.configure(image=character_photo)

    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()

    if CHARACTER_X is None:
        x = (screen_w - img_w) // 2
    else:
        x = CHARACTER_X

    if CHARACTER_Y is None:
        y = (screen_h - img_h) // 2
    else:
        y = CHARACTER_Y

    # 画面外にはみ出さないように補正
    x = max(0, min(x, screen_w - img_w))
    y = max(0, min(y, screen_h - img_h))

    character_window.geometry(f"{img_w}x{img_h}+{x}+{y}")
    character_window.deiconify()
    character_window.lift()
    character_window.update()


def hide_character():
    """
    キャラ画像を非表示にする
    """
    character_window.withdraw()
    root.update()


def wait_seconds_with_window(seconds):
    """
    キャラ表示を維持しながら待つ
    """
    end_time = time.time() + seconds

    while time.time() < end_time:
        root.update()
        time.sleep(0.03)


# =====================
# カメラ初期化
# =====================
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
cap.set(cv2.CAP_PROP_FPS, CAMERA_FPS)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

actual_width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
actual_height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
actual_fps = cap.get(cv2.CAP_PROP_FPS)

print(f"Camera: {actual_width} x {actual_height}, FPS: {actual_fps}")

fgbg = cv2.createBackgroundSubtractorMOG2(
    history=200,
    varThreshold=50,
    detectShadows=False
)

# =====================
# 状態管理
# =====================
start_time = time.time()
last_detected_time = 0
last_motion_time = 0

# True のときだけ検知イベントを発火できる
armed = True


def play_bell_and_voice(sound, label):
    """
    ベルと指定音声を同時に鳴らす
    """
    print(f"ベル + 音声を同時再生: {label}")

    bell_sound.play()
    sound.play()


def play_bell_and_random_voice():
    """
    ベルとランダム音声を同時に鳴らす
    """
    if len(voice_sounds) == 0:
        print("ランダム音声がないため、ベルのみ再生します")
        bell_sound.play()
        return

    voice_name, voice_sound = random.choice(voice_sounds)
    play_bell_and_voice(voice_sound, voice_name)


def play_sequence():
    """
    検知時:
    キャラ画像を表示

    1回目: ベル + 固定『いらっしゃいませ』
    3秒待つ

    2回目: ベル + ランダム音声
    3秒待つ

    3回目: ベル + ランダム音声
    3秒待つ

    最後にキャラ画像を消す
    """
    show_character()

    try:
        # 1回目
        print("1回目の再生")

        if welcome_sound is not None:
            play_bell_and_voice(welcome_sound, welcome_file_name)
        else:
            print("固定音声がないため、ベルのみ再生します")
            bell_sound.play()

        wait_seconds_with_window(3)

        # 2回目
        print("2回目の再生")
        play_bell_and_random_voice()
        wait_seconds_with_window(3)

        # 3回目
        print("3回目の再生")
        play_bell_and_random_voice()
        wait_seconds_with_window(3)

    finally:
        hide_character()


try:
    while True:
        root.update()

        ret, frame = cap.read()

        if not ret:
            print("カメラを取得できません")
            break

        frame = cv2.resize(frame, (CAMERA_WIDTH, CAMERA_HEIGHT))
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        fgmask = fgbg.apply(gray)

        fgmask = cv2.GaussianBlur(fgmask, (5, 5), 0)
        _, thresh = cv2.threshold(fgmask, 200, 255, cv2.THRESH_BINARY)

        contours, _ = cv2.findContours(
            thresh,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )

        human_like_motion = False

        for contour in contours:
            area = cv2.contourArea(contour)

            if area > MIN_AREA:
                human_like_motion = True
                break

        now = time.time()

        # =====================
        # 起動直後の誤検知を無視
        # =====================
        if now - start_time < STARTUP_IGNORE_SECONDS:
            if human_like_motion:
                print("起動直後のため検知を無視しています")
            continue

        # =====================
        # 動きの有無を記録
        # =====================
        if human_like_motion:
            last_motion_time = now

        # =====================
        # 動きが消えたら再検知可能に戻す
        # =====================
        if not human_like_motion and not armed:
            if now - last_motion_time > MOTION_CLEAR_SECONDS:
                print("動きが消えたため、再検知可能に戻します")
                armed = True

        # =====================
        # 検知イベント
        # =====================
        if (
            human_like_motion
            and armed
            and now - last_detected_time > cooldown
        ):
            print("人の動きらしきものを検知しました")

            # 同じ動きで2回発火しないようにする
            armed = False

            # 検知した瞬間に更新
            last_detected_time = now
            last_motion_time = now

            play_sequence()

        # デバッグ用にカメラ映像を出したい場合だけ使う
        # cv2.imshow("Camera", frame)
        # cv2.imshow("Motion Mask", thresh)
        # if cv2.waitKey(1) & 0xFF == ord("q"):
        #     break

except KeyboardInterrupt:
    print("終了します")

finally:
    cap.release()
    hide_character()
    character_window.destroy()
    root.destroy()
    cv2.destroyAllWindows()
    pygame.mixer.quit()