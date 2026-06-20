import cv2
import time
import random
import shutil
import subprocess
import tkinter as tk
from pathlib import Path
from PIL import Image, ImageTk

# =====================
# 設定
# =====================
CHARACTER_IMAGE_FILE = "character.png"

MOVIE_DIR = Path("movies")
MOVIE_EXTENSIONS = [".mp4", ".mov", ".avi", ".mkv"]
WELCOME_MOVIE_FILE = "0620 (1).mp4"

CAMERA_WIDTH = 320
CAMERA_HEIGHT = 240
CAMERA_FPS = 15
CAMERA_INDEXES_TO_TRY = [1, 2, 3, 4, 0]

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
# 動画初期化
# =====================
movie_files = [
    p for p in MOVIE_DIR.iterdir()
    if p.is_file() and p.suffix.lower() in MOVIE_EXTENSIONS
]

welcome_movie = MOVIE_DIR / WELCOME_MOVIE_FILE
random_movie_files = [
    p for p in movie_files
    if p.name != WELCOME_MOVIE_FILE
]

if not welcome_movie.exists():
    print(f"固定動画が見つかりません: {welcome_movie}")

if len(random_movie_files) == 0:
    print("ランダム再生用の動画ファイルがありません")

print(f"固定動画: {welcome_movie.name if welcome_movie.exists() else None}")
print(f"ランダム動画数: {len(random_movie_files)}")

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

def play_sequence():
    """
    検知時に、固定動画を1本、ランダム動画を2本再生する
    """
    if welcome_movie.exists():
        play_movie(welcome_movie)
    else:
        print("固定動画がないため、1本目をスキップします")

    if len(random_movie_files) == 0:
        print("ランダム動画がないため、追加再生をスキップします")
        return

    selected_movies = random.sample(
        random_movie_files,
        k=min(2, len(random_movie_files)),
    )

    for movie_path in selected_movies:
        play_movie(movie_path)


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


def play_movie_with_cv2(movie_path):
    video = cv2.VideoCapture(str(movie_path))

    if not video.isOpened():
        print(f"動画を開けません: {movie_path}")
        return

    fps = video.get(cv2.CAP_PROP_FPS)
    delay_ms = int(1000 / fps) if fps and fps > 0 else 33

    while True:
        ret, frame = video.read()

        if not ret:
            break

        cv2.imshow("Movie", frame)
        root.update()

        if cv2.waitKey(delay_ms) & 0xFF == ord("q"):
            break

    video.release()
    cv2.destroyWindow("Movie")


def play_movie(movie_path):
    print(f"動画再生: {movie_path.name}")

    ffplay_path = shutil.which("ffplay")

    if ffplay_path is None:
        print("ffplayが見つからないため、映像のみ再生します")
        play_movie_with_cv2(movie_path)
        return

    subprocess.run(
        [
            ffplay_path,
            "-autoexit",
            "-loglevel",
            "quiet",
            "-window_title",
            movie_path.name,
            str(movie_path),
        ],
        check=False,
    )


def apply_camera_settings(camera):
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
    camera.set(cv2.CAP_PROP_FPS, CAMERA_FPS)
    camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)


def open_preferred_camera():
    """
    内蔵カメラになりやすい0番を後回しにして、USBカメラを優先する
    """
    for camera_index in CAMERA_INDEXES_TO_TRY:
        camera = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
        apply_camera_settings(camera)

        if not camera.isOpened():
            camera.release()
            continue

        ret, _ = camera.read()

        if ret:
            print(f"Camera index: {camera_index}")
            return camera

        camera.release()

    return None


# =====================
# カメラ初期化
# =====================
cap = open_preferred_camera()

if cap is None:
    print("使用できるカメラが見つかりません")
    root.destroy()
    raise SystemExit(1)

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
