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
