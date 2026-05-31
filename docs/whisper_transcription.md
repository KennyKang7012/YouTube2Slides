# Whisper 語音辨識整合說明

當 YouTube 影片沒有字幕，或字幕品質不佳時，可啟用 Whisper 語音辨識從影片音訊自動生成字幕。

## 支援的提供商

| 提供商 | 模型 | 特性 |
|--------|------|------|
| **OpenAI** | `whisper-1` | 官方原版，穩定可靠；支援 `timestamp_granularities=["segment"]` 取得更自然的句子斷點 |
| **Groq** | `whisper-large-v3-turbo` | 速度更快（通常 10x+）、費用更低；[免費方案](https://console.groq.com/)可使用 |

## API Key 設定

兩種方式可擇一或並用，**UI 輸入優先於環境變數**：

### 方式 A：UI 輸入（per-request）
在前端「使用 AI 生成字幕」區塊直接輸入，Key 僅用於當次請求，不存於伺服器。

### 方式 B：環境變數（伺服器預設）
在 `backend/.env` 設定：

```
OPENAI_API_KEY=sk-...      # OpenAI Whisper
GROQ_API_KEY=gsk_...       # Groq Whisper
```

設定後，UI 的 API Key 欄位可留空，後端自動讀取。

## 技術細節

### 流程

```
影片 (.mp4)
  → extract_audio_from_video()   # ffmpeg 抽取音訊為 .mp3（16kHz mono）
  → transcribe_audio()           # 呼叫 Whisper API
  → save_transcription_as_srt()  # 轉為 SRT 字幕檔
  → 儲存至 storage/subtitles/{video_id}.{lang}.srt
```

### 提供商分支邏輯（`audio_transcription.py`）

```python
if provider == "groq":
    client = Groq(api_key=used_api_key)
    transcription = client.audio.transcriptions.create(
        model="whisper-large-v3-turbo",
        response_format="verbose_json",
        language=language
    )
else:  # openai
    client = OpenAI(api_key=used_api_key)
    transcription = client.audio.transcriptions.create(
        model="whisper-1",
        response_format="verbose_json",
        timestamp_granularities=["segment"],  # Groq 不支援此參數
        language=language
    )
```

> `timestamp_granularities=["segment"]` 僅 OpenAI 支援，可獲得更自然的句子級斷點。Groq 預設也會回傳 segments，但斷點由模型自行決定。

### Schema 欄位（`ProcessVideoRequest`）

| 欄位 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| `use_ai_transcription` | `bool` | `false` | 是否啟用 Whisper |
| `whisper_provider` | `WhisperProvider` | `"openai"` | 提供商（`openai` / `groq`） |
| `whisper_api_key` | `str \| null` | `null` | API Key（留空則讀 .env） |

### Key 解析優先順序

```python
# audio_transcription.py
used_api_key = api_key or self.openai_api_key  # OpenAI
used_api_key = api_key or self.groq_api_key    # Groq
```

若兩者皆無，後端拋出明確錯誤訊息提示補充 Key。

## 注意事項

- Whisper 處理時間與影片長度成正比，長影片可能需要數分鐘
- 音訊暫存於 `storage/audio/{video_id}.mp3`，轉錄完成後自動刪除
- 語言自動偵測（`language=None`），也可透過前端字幕語言設定指定
- Groq 免費方案有每分鐘請求數限制，長影片建議使用 OpenAI 或付費方案

---

## 已知問題與修正

### `.env` API Key 無法生效（2026-05-30 修正）

**症狀**

在 `backend/.env` 設定 `GROQ_API_KEY`（或其他 Key），UI 欄位留空，執行 AI 字幕生成時仍報錯：

```
Groq API key is required. Provide it in the UI or set GROQ_API_KEY in backend/.env
```

**根本原因**

`app.py` 從未呼叫 `load_dotenv()`，`.env` 檔案的內容永遠不會被載入到環境變數。
各 service 在 module 初始化時執行 `os.getenv("GROQ_API_KEY")` 拿到的永遠是 `None`，
UI 留空時 fallback 也是 `None`，因此報錯。

此 bug 影響所有透過 `.env` 設定的 Key：

| 環境變數 | 影響功能 |
|---|---|
| `GROQ_API_KEY` | Groq Whisper 字幕生成 |
| `OPENAI_API_KEY` | OpenAI Whisper 字幕生成、AI 翻譯/大綱 |
| `ANTHROPIC_API_KEY` | Claude AI 翻譯/大綱 |
| `GEMINI_API_KEY` | Gemini AI 翻譯/大綱 |

**修正方式**

在 `backend/app.py` 所有 service 初始化之前加入：

```python
from dotenv import load_dotenv
load_dotenv()  # Must be called before any os.getenv() in service __init__
```

**為什麼 UI 直接輸入 Key 可以繞過此問題**

UI 輸入的 Key 透過 `request.whisper_api_key` 直接傳入，不經過 `os.getenv()`，
因此即使 `.env` 未載入也能正常運作。修正後，UI 留空才能正確 fallback 到 `.env`。

---

### Groq Segments 回傳 dict 導致 AttributeError（2026-05-31 修正）

**症狀**

選擇 Groq 提供商執行 AI 字幕生成時，後端報錯：

```
AttributeError: 'dict' object has no attribute 'start'
```

完整錯誤路徑：

```
save_transcription_as_srt()
  → segment.start  ← AttributeError
```

**根本原因**

OpenAI SDK 的 `transcriptions.create()` 回傳的 `segments` 是**物件列表**（可用 `segment.start`），
但 Groq SDK 回傳的 `segments` 是**dict 列表**（需用 `segment['start']`）。

原始程式碼只考慮 OpenAI 格式：

```python
# 原始（只支援 OpenAI）
start_time = self._format_timestamp_srt(segment.start)
end_time   = self._format_timestamp_srt(segment.end)
text       = segment.text.strip()
```

**修正方式**

在 `save_transcription_as_srt()` 加入型別判斷（`audio_transcription.py:160`）：

```python
if isinstance(segment, dict):
    start_time = self._format_timestamp_srt(segment['start'])
    end_time   = self._format_timestamp_srt(segment['end'])
    text       = segment['text'].strip()
else:
    start_time = self._format_timestamp_srt(segment.start)
    end_time   = self._format_timestamp_srt(segment.end)
    text       = segment.text.strip()
```

OpenAI 與 Groq 兩個提供商皆可正常產生 SRT 字幕。
