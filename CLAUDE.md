# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

YouTube2Slides 是一個將 YouTube 影片轉換為靜態可讀投影片的 Web 應用程式。使用者可以輸入 YouTube URL，系統會：
1. 下載影片並提取字幕
2. 根據字幕時間軸自動截取關鍵幀
3. 使用 AI 翻譯字幕（可選）
4. 生成 AI 影片大綱（可選）
5. 在前端瀏覽器中展示投影片與字幕

## Python 環境管理

本專案使用 **uv** 作為 Python 套件管理工具：

- **安裝套件**: `uv add <package-name>`
- **執行 Python 程式**: `uv run python <script.py>`
- **同步依賴**: `cd backend && uv sync`

**IMPORTANT**: 所有 Python 命令都必須使用 `uv run` 前綴執行。

## 啟動服務

**後端** (FastAPI, port 8000):
```bash
cd backend
uv run python app.py
```

**前端** (React, port 3000):
```bash
cd frontend
npm install   # 首次執行
npm start
```

**API 文檔**: http://localhost:8000/docs

## 環境設定

**後端** (`backend/.env`，參考 `backend/.env.example`):
```
OPENAI_API_KEY=...       # AI 翻譯/大綱（OpenAI）、Whisper 語音辨識
ANTHROPIC_API_KEY=...    # AI 翻譯/大綱（Claude）
GEMINI_API_KEY=...       # AI 翻譯/大綱（Gemini）
GROQ_API_KEY=...         # Whisper 語音辨識（Groq，更快速）
```

**前端**: 若後端不在預設 `http://localhost:8000`，可設定 `REACT_APP_API_URL` 環境變數（`frontend/src/api/api.js`）。

## 核心架構

### 後端架構 (FastAPI)

**主要服務** (`backend/services/`):

1. **youtube.py**: 使用 `yt-dlp` 下載 YouTube 影片與字幕
2. **subtitle.py**: SRT 字幕解析、合併、時間軸處理
3. **frame_extractor.py**: 使用 `ffmpeg` 根據字幕時間截取影格
4. **translator.py**: Google Translate 批次翻譯（備用）
5. **ai_translator.py**: AI 翻譯服務（OpenAI/Claude/Gemini/Ollama）
   - 動態批次大小（根據字幕平均長度自動調整 10-30 項/批次）
   - 三種解析方法防止翻譯遺漏
6. **ai_outline.py**: AI 大綱生成服務
7. **audio_transcription.py**: Whisper API 音訊轉字幕，支援 OpenAI（`whisper-1`）與 Groq（`whisper-large-v3-turbo`）兩個提供商
8. **subtitle_optimizer.py**: 字幕斷行與格式優化

**資料模型** (`backend/models/schemas.py`):
- `ProcessVideoRequest`: 包含 `quality`, `subtitle_languages`, `translate_to`, `screenshot_position`, `generate_outline`, `ai_provider`, `ai_model`, `api_key`, `use_ai_transcription`, `whisper_api_key`
- `AIProvider` enum: `openai`, `claude`, `gemini`, `ollama`
- `JobStatusResponse`: 包含 `job_id`, `status`, `progress`, `history` (進度事件列表), `result`

**主要 API 端點** (`backend/app.py`):
- `POST /api/video/info`: 取得影片資訊
- `POST /api/video/process`: 處理影片（建立背景 job）
- `GET /api/jobs/{job_id}`: 查詢任務狀態
- `GET /api/videos/history`: 取得處理歷史記錄（從 `storage/results/` 讀取）
- `DELETE /api/video/{video_id}`: 刪除歷史記錄與檔案
- `GET /api/video/{video_id}/download-frames`: 下載影格 ZIP 包
- `GET /api/ai-providers`: 獲取可用 AI 提供商
- `GET /api/ollama/models`: 獲取 Ollama 本機模型列表

**重要邏輯**:
- **Job 狀態儲存在記憶體** (`jobs: Dict`): 後端重啟後 job 狀態消失，但結果已持久化至 `storage/results/{video_id}.json`
- **AI 翻譯觸發條件** (`app.py:456`): 需要 `request.generate_outline and request.ai_provider` 同時為真；否則使用 Google Translate
- **AI 翻譯失敗時自動降級**至 Google Translate（見 `app.py` exception handler）

### 前端架構 (React)

**主要組件** (`frontend/src/components/`):

1. **VideoInput.js**: 影片 URL 輸入表單（畫質、字幕語言、翻譯選項、AI 設定）
2. **ProcessingStatus.js**: 每 2 秒輪詢 `/api/jobs/{job_id}` 顯示進度
3. **SlideViewer.js**: 投影片檢視器（鍵盤導航、縮圖、字幕同步、AI 大綱）
4. **Sidebar.js**: 歷史記錄側邊欄（資料夾管理、拖放排序）

**工具函數** (`frontend/src/utils/`):

1. **historyManager.js**: localStorage 管理
   - `syncHistoryFromBackend()`: 合併後端資料，保留本地 `folderId`（後端不儲存 `folderId`）
   - `moveHistoryToFolder()`, `reorderHistory()`: 資料夾與排序操作
   - localStorage keys: `videoHistory`, `historyFolders`, `lastHistorySync`

2. **settingsManager.js**: 使用者設定管理（AI provider、model、API keys）→ `userSettings`

**資料流**:
1. `App.js` 呼叫 `processVideo()` → 後端建立 job，返回 `job_id`
2. `pollJobStatus()` 每 2 秒輪詢直到完成或失敗
3. 完成後儲存至 `historyManager` (localStorage) + 後端 `/api/video/history`

### 儲存結構

**storage/** 目錄（由後端管理）:
```
storage/
├── results/
│   └── {video_id}.json            # 持久化處理結果（歷史記錄來源）
├── subtitles/
│   └── {video_id}.{lang}.translated.srt
├── frames/
│   └── {video_id}/
│       ├── frame_0001.jpg
│       └── ...
└── {job_id}/
    ├── video.mp4
    └── original_subtitle.srt
```

注意：翻譯後字幕存至 `storage/subtitles/`，不在 `{job_id}/` 目錄內。

## 常見開發任務

### 新增 AI 提供商

1. 在 `backend/models/schemas.py` 的 `AIProvider` enum 新增值
2. 在 `ai_translator.py` 和 `ai_outline.py` 新增對應實作分支
3. 在 `VideoInput.js` 新增選項

### 修改 AI 翻譯提示詞

編輯 `backend/services/ai_translator.py` 的 `_get_translation_prompt()`。當前提示詞包含 7 條規則，強調自然翻譯、保留格式、42 字符長度限制。

### 調整翻譯批次大小策略

修改 `backend/services/ai_translator.py` 的 `_calculate_optimal_batch_size()`。

## 疑難排解

### ffmpeg 找不到
```bash
brew install ffmpeg          # macOS
sudo apt install ffmpeg      # Linux
choco install ffmpeg         # Windows
```

### 虛擬環境問題
```bash
cd backend && uv sync
```

### AI 翻譯不觸發
必須同時勾選「AI 翻譯 & 生成 AI 影片大綱」**且**選擇 AI 提供商。邏輯在 `app.py:456`。

### 資料夾分類遺失
`syncHistoryFromBackend()` 應保留本地 `folderId`；後端不儲存此欄位。

## 測試

本專案目前無自動化測試。功能驗證需手動透過瀏覽器操作。
