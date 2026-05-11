import asyncio
import base64
import io
import logging
import os
import random
import textwrap
from dataclasses import dataclass
from typing import Dict, List, Optional

import qrcode
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import BufferedInputFile, Message
from aiogram.utils.markdown import hbold
from dotenv import load_dotenv
from openai import OpenAI
from openai import APIError, APIStatusError, RateLimitError
from PIL import Image, ImageDraw, ImageFont
import yt_dlp


load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("omnibot")


START_MESSAGE = (
    "Chào bạn! Mình là OmniBot. 🚀 Mình có thể giúp bạn:\n\n"
    "✍️ Chat & Viết lách\n"
    "🎨 Tạo ảnh nghệ thuật\n"
    "🖼️ Chế Meme hài hước\n"
    "🔗 Tạo mã QR nhanh\n"
    "🧠 Thử thách câu đố (Quiz)\n"
    "📥 Tải video đa nền tảng\n\n"
    "Bạn cần mình hỗ trợ gì ngay bây giờ không?"
)

HELP_MESSAGE = (
    f"{hbold('OmniBot Commands')}\n"
    "- /start: Chào mừng\n"
    "- /help: Hướng dẫn nhanh\n"
    "- /image [mô tả]: Tạo prompt ảnh tiếng Anh (DALL-E style)\n"
    "- /qr [nội dung]: Tạo mã QR\n"
    "- /meme [text trên] | [text dưới]: Tạo meme nhanh\n"
    "- /quiz [chủ đề]: Tạo câu đố 4 lựa chọn\n"
    "- /video [url]: Lấy link video trực tiếp chất lượng cao\n\n"
    "Bạn cũng có thể chat tự nhiên, bot sẽ trả lời bằng tiếng Việt."
)

SYSTEM_PROMPT = """
Bạn là OmniBot – Trợ Lý Đa Năng 6-trong-1 trên Telegram.
- Luôn trả lời bằng ngôn ngữ người dùng dùng (mặc định Tiếng Việt).
- Trả lời ngắn gọn, rõ ràng, lịch sự, hữu ích.
- Từ chối nội dung độc hại, NSFW, vi phạm pháp luật hoặc bản quyền.
- Khi người dùng yêu cầu tạo ảnh, hãy trả prompt tiếng Anh thật chi tiết theo phong cách DALL-E 3.
""".strip()

PROMPT_IMAGE_POLISH = (
    "Convert the following Vietnamese image request into one polished, detailed English prompt "
    "for DALL-E 3 style generation. Include subject, setting, composition, lighting, mood, quality, "
    "lens/camera style, and color palette. Keep it as one paragraph.\n\nRequest: "
)


@dataclass
class QuizItem:
    topic: str
    question: str
    options: List[str]
    correct_index: int
    explanation: str


QUIZ_DB: Dict[str, List[QuizItem]] = {
    "cntt": [
        QuizItem(
            topic="CNTT",
            question="Giao thức nào dùng để truyền tải web an toàn?",
            options=["HTTP", "FTP", "HTTPS", "SMTP"],
            correct_index=2,
            explanation="HTTPS mã hóa kết nối bằng TLS/SSL, giúp bảo vệ dữ liệu truyền đi.",
        )
    ],
    "lich su": [
        QuizItem(
            topic="Lịch sử",
            question="Chiến thắng Điện Biên Phủ diễn ra vào năm nào?",
            options=["1945", "1954", "1968", "1975"],
            correct_index=1,
            explanation="Chiến thắng Điện Biên Phủ diễn ra năm 1954.",
        )
    ],
    "toan": [
        QuizItem(
            topic="Toán",
            question="Giá trị của 2^5 là bao nhiêu?",
            options=["10", "16", "32", "64"],
            correct_index=2,
            explanation="2^5 = 32.",
        )
    ],
    "giai tri": [
        QuizItem(
            topic="Giải trí",
            question="Phim hoạt hình nào có nhân vật chính là chú sư tử Simba?",
            options=["Frozen", "The Lion King", "Shrek", "Up"],
            correct_index=1,
            explanation="Simba là nhân vật chính trong The Lion King.",
        )
    ],
}

pending_quiz: Dict[int, QuizItem] = {}


def build_openai_client() -> Optional[OpenAI]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    base_url = os.getenv("OPENAI_BASE_URL")
    if base_url:
        return OpenAI(api_key=api_key, base_url=base_url)
    return OpenAI(api_key=api_key)


OPENAI_CLIENT = build_openai_client()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_IMAGE_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1")


def chat_completion(user_text: str) -> str:
    if not OPENAI_CLIENT:
        return (
            "Mình chưa được cấu hình AI API. Hãy set `OPENAI_API_KEY` để bật chat thông minh nhé."
        )

    try:
        resp = OPENAI_CLIENT.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_text},
            ],
            temperature=0.7,
        )
        return resp.choices[0].message.content or "Mình chưa tạo được phản hồi, bạn thử lại nhé."
    except RateLimitError:
        return (
            "Hiện quota OpenAI đã hết hoặc đang bị giới hạn tốc độ. "
            "Bạn nạp thêm billing hoặc thử lại sau nhé."
        )
    except (APIStatusError, APIError):
        logger.exception("OpenAI API error in chat_completion")
        return "Mình đang gặp lỗi khi gọi AI. Bạn thử lại sau ít phút nhé."
    except Exception:
        logger.exception("Unexpected error in chat_completion")
        return "Mình tạm thời chưa trả lời AI được. Bạn thử lại sau nhé."


def polish_image_prompt(vn_request: str) -> str:
    if not OPENAI_CLIENT:
        return (
            "A highly detailed digital artwork of "
            f"{vn_request}, cinematic lighting, rich color palette, ultra sharp focus, 4k."
        )
    try:
        resp = OPENAI_CLIENT.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "You are a world-class prompt engineer."},
                {"role": "user", "content": PROMPT_IMAGE_POLISH + vn_request},
            ],
            temperature=0.8,
        )
        return resp.choices[0].message.content or "Could not generate prompt."
    except RateLimitError:
        # Keep image command usable even when quota is exhausted.
        return (
            "A highly detailed digital artwork of "
            f"{vn_request}, cinematic lighting, rich color palette, ultra sharp focus, 4k."
        )
    except (APIStatusError, APIError):
        logger.exception("OpenAI API error in polish_image_prompt")
        return (
            "A cinematic, highly detailed scene based on "
            f"{vn_request}, dramatic lighting, vivid colors, ultra high resolution, 4k."
        )
    except Exception:
        logger.exception("Unexpected error in polish_image_prompt")
        return (
            "A visually striking digital artwork inspired by "
            f"{vn_request}, dynamic composition, rich textures, 4k."
        )


def generate_image_bytes(prompt: str) -> bytes:
    if not OPENAI_CLIENT:
        raise RuntimeError("MISSING_API_KEY")

    response = OPENAI_CLIENT.images.generate(
        model=OPENAI_IMAGE_MODEL,
        prompt=prompt,
        size="1024x1024",
    )
    data = response.data[0]
    b64 = getattr(data, "b64_json", None)
    if not b64:
        raise RuntimeError("IMAGE_DATA_EMPTY")
    return base64.b64decode(b64)


def make_qr_png(data: str) -> bytes:
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    stream = io.BytesIO()
    img.save(stream, format="PNG")
    return stream.getvalue()


def create_meme_image(top_text: str, bottom_text: str) -> bytes:
    width, height = 1080, 1080
    image = Image.new("RGB", (width, height), color=(30, 30, 30))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()

    wrapped_top = "\n".join(textwrap.wrap(top_text.upper(), width=24))
    wrapped_bottom = "\n".join(textwrap.wrap(bottom_text.upper(), width=24))

    draw.multiline_text((40, 40), wrapped_top, fill="white", font=font, spacing=8)
    draw.multiline_text((40, height - 180), wrapped_bottom, fill="white", font=font, spacing=8)

    bio = io.BytesIO()
    image.save(bio, format="PNG")
    return bio.getvalue()


def get_quiz(topic_text: str) -> QuizItem:
    normalized = topic_text.strip().lower()
    for key, items in QUIZ_DB.items():
        if key in normalized:
            return random.choice(items)
    return random.choice(random.choice(list(QUIZ_DB.values())))


def _pick_best_direct_url(info: dict) -> Optional[str]:
    if not info:
        return None

    # Some extractors return a playlist-like object.
    if info.get("_type") == "playlist" and info.get("entries"):
        first = next((entry for entry in info["entries"] if entry), None)
        if first:
            info = first

    if info.get("url"):
        return info["url"]

    formats = info.get("formats") or []
    mp4_formats = [f for f in formats if f.get("url") and f.get("ext") == "mp4"]
    if mp4_formats:
        mp4_formats.sort(
            key=lambda f: (f.get("height") or 0, f.get("tbr") or 0),
            reverse=True,
        )
        return mp4_formats[0]["url"]

    any_formats = [f for f in formats if f.get("url")]
    if any_formats:
        any_formats.sort(
            key=lambda f: (f.get("height") or 0, f.get("tbr") or 0),
            reverse=True,
        )
        return any_formats[0]["url"]

    return None


def extract_direct_video_url(url: str) -> str:
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,
        "format": "best[ext=mp4]/best",
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        direct_url = _pick_best_direct_url(info)
        if not direct_url:
            raise ValueError("Không trích xuất được URL video trực tiếp.")
        return direct_url


async def cmd_start(message: Message) -> None:
    await message.answer(START_MESSAGE)


async def cmd_help(message: Message) -> None:
    await message.answer(HELP_MESSAGE, parse_mode=ParseMode.HTML)


async def cmd_image(message: Message) -> None:
    args = message.text.removeprefix("/image").strip() if message.text else ""
    if not args:
        await message.answer("Dùng: /image [mô tả ảnh], ví dụ: /image vẽ con mèo bay trong vũ trụ")
        return
    await message.answer("Đang tạo ảnh cho bạn, chờ mình chút...")
    prompt = polish_image_prompt(args)
    try:
        image_bytes = await asyncio.to_thread(generate_image_bytes, prompt)
        photo = BufferedInputFile(image_bytes, filename="omnibot-image.png")
        await message.answer_photo(
            photo=photo,
            caption="Ảnh đã tạo xong 🎨",
        )
    except RateLimitError:
        await message.answer(
            "Không tạo được ảnh vì API đang giới hạn hoặc hết quota.\n\n"
            f"{hbold('Prompt tiếng Anh tối ưu:')}\n{prompt}",
            parse_mode=ParseMode.HTML,
        )
    except Exception as exc:
        logger.exception("Image generation failed")
        if str(exc) == "MISSING_API_KEY":
            await message.answer(
                "Chưa có `OPENAI_API_KEY` nên chưa render ảnh trực tiếp được.\n\n"
                f"{hbold('Prompt tiếng Anh tối ưu:')}\n{prompt}",
                parse_mode=ParseMode.HTML,
            )
        else:
            await message.answer(
                "Mình chưa render ảnh được lúc này. Bạn thử lại sau nhé.\n\n"
                f"{hbold('Prompt tiếng Anh tối ưu:')}\n{prompt}",
                parse_mode=ParseMode.HTML,
            )


async def cmd_qr(message: Message) -> None:
    args = message.text.removeprefix("/qr").strip() if message.text else ""
    if not args:
        await message.answer("Dùng: /qr [nội dung hoặc link]")
        return
    png_data = make_qr_png(args)
    photo = BufferedInputFile(png_data, filename="qr.png")
    await message.answer_photo(photo=photo, caption="QR của bạn đây ✅")


async def cmd_meme(message: Message) -> None:
    args = message.text.removeprefix("/meme").strip() if message.text else ""
    if "|" not in args:
        await message.answer("Dùng: /meme [text trên] | [text dưới]")
        return

    top_text, bottom_text = [part.strip() for part in args.split("|", maxsplit=1)]
    meme_data = create_meme_image(top_text or "TOP TEXT", bottom_text or "BOTTOM TEXT")
    photo = BufferedInputFile(meme_data, filename="meme.png")
    await message.answer_photo(photo=photo, caption="Meme mới nóng hổi 🤡")


async def cmd_quiz(message: Message) -> None:
    topic = message.text.removeprefix("/quiz").strip() if message.text else ""
    quiz = get_quiz(topic or "random")
    pending_quiz[message.from_user.id] = quiz

    options = "\n".join(
        f"{label}. {choice}" for label, choice in zip(["A", "B", "C", "D"], quiz.options)
    )
    await message.answer(
        f"🧠 Chủ đề: {quiz.topic}\n\n"
        f"{hbold('Câu hỏi:')} {quiz.question}\n\n"
        f"{options}\n\n"
        "Trả lời bằng A/B/C/D nhé. Muốn thoát quiz: /cancelquiz"
    )


async def cmd_cancel_quiz(message: Message) -> None:
    if not message.from_user:
        await message.answer("Không xác định được người dùng để hủy quiz.")
        return

    if pending_quiz.pop(message.from_user.id, None):
        await message.answer("Đã hủy quiz hiện tại.")
    else:
        await message.answer("Bạn chưa có quiz nào đang chạy.")


async def cmd_video(message: Message) -> None:
    args = message.text.removeprefix("/video").strip() if message.text else ""
    if not args:
        await message.answer("Dùng: /video [link TikTok/YouTube/Facebook/Instagram]")
        return

    await message.answer("Đang trích xuất link MP4 chất lượng cao nhất có thể, chờ mình chút...")
    try:
        direct_url = await asyncio.to_thread(extract_direct_video_url, args)
        await message.answer(
            f"{hbold('Link tải trực tiếp (MP4):')}\n{direct_url}",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
    except Exception as exc:
        logger.exception("Video extraction failed")
        await message.answer(
            "Mình chưa lấy được link trực tiếp từ URL này. "
            "Bạn thử link công khai khác (không private/giới hạn tuổi/vùng) nhé.\n\n"
            f"Chi tiết lỗi: {exc}"
        )


async def handle_quiz_answer(message: Message) -> bool:
    if not message.from_user:
        return False
    user_id = message.from_user.id
    if user_id not in pending_quiz:
        return False
    if not message.text:
        return False

    answer = message.text.strip().upper()
    mapping = {"A": 0, "B": 1, "C": 2, "D": 3}
    cancel_tokens = {"HUY", "HỦY", "BO", "BỎ", "SKIP", "CANCEL", "/CANCELQUIZ"}

    if answer in cancel_tokens:
        pending_quiz.pop(user_id, None)
        await message.answer("Đã hủy quiz. Bạn có thể chat bình thường hoặc /quiz lại.")
        return True

    if answer not in mapping:
        # If user sends regular text, auto-exit quiz so they are not stuck.
        pending_quiz.pop(user_id, None)
        await message.answer(
            "Mình đã thoát quiz vì bạn gửi tin nhắn thường. "
            "Gõ /quiz để chơi lại nhé."
        )
        return True

    quiz = pending_quiz.pop(user_id)
    is_correct = mapping[answer] == quiz.correct_index
    result = "✅ Chính xác!" if is_correct else "❌ Chưa đúng!"
    correct_label = ["A", "B", "C", "D"][quiz.correct_index]
    await message.answer(
        f"{result}\n"
        f"Đáp án đúng: {correct_label}. {quiz.options[quiz.correct_index]}\n"
        f"Giải thích: {quiz.explanation}"
    )
    return True


async def handle_chat(message: Message) -> None:
    if await handle_quiz_answer(message):
        return

    if not message.text:
        await message.answer("Mình hiện hỗ trợ xử lý text trước, bạn gửi câu hỏi chữ nhé.")
        return

    reply = chat_completion(message.text)
    await message.answer(reply)


def register_handlers(dp: Dispatcher) -> None:
    dp.message.register(cmd_start, CommandStart())
    dp.message.register(cmd_help, Command("help"))
    dp.message.register(cmd_image, Command("image"))
    dp.message.register(cmd_qr, Command("qr"))
    dp.message.register(cmd_meme, Command("meme"))
    dp.message.register(cmd_quiz, Command("quiz"))
    dp.message.register(cmd_cancel_quiz, Command("cancelquiz"))
    dp.message.register(cmd_video, Command("video"))
    dp.message.register(handle_chat, F.text | F.caption)


async def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Thiếu TELEGRAM_BOT_TOKEN trong môi trường.")

    bot = Bot(token=token)
    dp = Dispatcher()
    register_handlers(dp)
    logger.info("OmniBot is running...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
