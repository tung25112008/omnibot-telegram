# OmniBot Telegram (6-trong-1)

Bot Telegram đa năng gồm:
- Chat AI
- Tạo prompt ảnh (`/image`)
- Tạo QR (`/qr`)
- Tạo meme nhanh (`/meme`)
- Quiz trắc nghiệm (`/quiz`)
- Trích xuất link video trực tiếp (`/video`)

## 1) Cài đặt

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 2) Cấu hình

1. Copy `.env.example` thành `.env`
2. Điền:
   - `TELEGRAM_BOT_TOKEN` (bắt buộc)
   - `OPENAI_API_KEY` (khuyến nghị để chat thông minh và tối ưu prompt ảnh)

## 3) Chạy bot

```bash
python bot.py
```

## 4) Lệnh hỗ trợ

- `/start`
- `/help`
- `/image vẽ con mèo bay trong vũ trụ`
- `/qr https://example.com`
- `/meme đi làm ngày thứ 2 | nhìn deadline tới`
- `/quiz cntt`
- `/video <video_url>`

## 5) Deploy 24/7 với Railway (khuyên dùng)

### Bước A - Đưa code lên GitHub

```bash
cd C:\Users\PC\omnibot-telegram
git init
git add .
git commit -m "Init OmniBot"
git branch -M main
git remote add origin <repo_url>
git push -u origin main
```

### Bước B - Tạo service trên Railway

1. Vào [Railway](https://railway.app/) và đăng nhập.
2. Chọn **New Project** -> **Deploy from GitHub repo**.
3. Chọn repo `omnibot-telegram`.
4. Railway tự detect Python app và chạy `python bot.py` theo `Procfile`.

### Bước C - Set biến môi trường

Trong tab **Variables**, thêm:
- `TELEGRAM_BOT_TOKEN` (bắt buộc)
- `OPENAI_API_KEY` (tuỳ chọn, để chat thông minh)
- `OPENAI_MODEL` (tuỳ chọn, mặc định `gpt-4o-mini`)

### Bước D - Chạy và kiểm tra

- Vào tab **Deployments** để xem log.
- Nếu thấy `OmniBot is running...` là bot đã lên 24/7.
- Nhắn `/start` vào bot Telegram để test.

## 6) Deploy 24/7 với Render (alternative)

1. Push code lên GitHub.
2. Vào [Render](https://render.com/) -> **New** -> **Background Worker**.
3. Chọn repo `omnibot-telegram`.
4. Cấu hình:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python bot.py`
5. Thêm biến môi trường giống Railway.

## Ghi chú

- Tính năng `/video` dùng `yt-dlp`, phụ thuộc nền tảng nguồn và giới hạn nội dung công khai.
- Bot đã có guardrails cơ bản: từ chối nội dung độc hại/nhạy cảm/vi phạm.
