# 影片處理快取機制

當使用者對同一支影片重複提交處理請求時，快取機制會直接返回已存在的結果，跳過所有耗費時間與費用的步驟（下載、字幕、翻譯、截圖）。

## 背景

AI 翻譯（OpenAI / Claude / Gemini）依照字幕數量計費。若使用者因 server 重啟、前端錯誤或誤操作而重複送出相同影片，會重複扣費。

實際案例：一支 427 段字幕的影片，每次翻譯耗費一筆 API 費用。Server 因 Ctrl+C 中斷後，若無快取機制，重跑會再扣一次。

## 快取邏輯

快取發生在 `backend/app.py` 的 `process_video_task()` 中，取得 `video_id` 之後、下載影片之前：

```python
# 快取檢查 — 若結果已存在則跳過所有處理
quality = request.quality.value
result_file = RESULTS_DIR / f"{video_id}_{quality}.json"
if result_file.exists():
    with open(result_file, 'r', encoding='utf-8') as f:
        cached = json.load(f)
    jobs[job_id]["result"] = cached.get('result', {})
    log_job_progress(job_id, step="complete", status=JobStatus.COMPLETED,
                     progress=100, message="已載入快取結果，略過重新處理")
    return
```

## 快取檔案命名規則

```
storage/results/{video_id}_{quality}.json
```

| 範例 | 說明 |
|------|------|
| `N30XGyPrr6I_720.json` | 影片 N30XGyPrr6I 以 720p 處理的結果 |
| `N30XGyPrr6I_1080.json` | 同影片以 1080p 處理的結果 |

**不同畫質各自獨立快取**，提交同一影片但選擇不同畫質時，不會命中彼此的快取，而是重新處理並儲存新的快取檔。

## 快取命中條件

`video_id` **AND** `quality` 兩者必須完全一致才會命中：

| video_id | quality | 結果 |
|----------|---------|------|
| 相同 | 相同 | ✅ 命中快取，直接返回 |
| 相同 | 不同 | ❌ 未命中，重新處理 |
| 不同 | 任意 | ❌ 未命中，重新處理 |

## 如何強制重新處理

若需要對同一支影片（相同畫質）重新處理（例如更換翻譯語言），在前端歷史記錄側邊欄刪除該影片即可。

刪除時後端會清除所有相關快取（`DELETE /api/video/{video_id}`）：

```python
# 刪除所有畫質的快取檔
result_files = list(RESULTS_DIR.glob(f"{video_id}_*.json")) + [RESULTS_DIR / f"{video_id}.json"]
for result_path in result_files:
    if result_path.exists():
        result_path.unlink()
```

## 快取失效情況

- 快取檔案被手動刪除
- 透過前端「刪除」功能移除該影片記錄
- 快取 JSON 損毀（讀取失敗時會 fallback 至完整流程，並在 log 印出警告）

```python
except Exception as e:
    print(f"[Cache] Failed to load cached result for {video_id}, proceeding with full processing: {e}")
```

---

## 翻譯快取（跨畫質共用）

翻譯結果與畫質無關，只取決於影片字幕內容。因此翻譯快取採用**不含畫質**的獨立命名：

```
storage/subtitles/{video_id}.{lang}.translated.srt
```

在翻譯步驟執行前，先檢查此檔案是否已存在：

```python
if Path(translated_subtitle_path).exists():
    cached_segs = subtitle_processor.parse_srt(translated_subtitle_path)
    cached_texts = [seg.text for seg in cached_segs]
    if len(cached_texts) == len(original_subtitle_texts):
        translated_subtitle_texts = cached_texts
        # 直接使用快取，跳過 API 呼叫
```

段數不吻合時（例如字幕來源有異動）會自動降級重新翻譯，不會使用錯誤的快取。

### 快取命中矩陣（完整）

| 操作 | 結果快取 | 翻譯快取 |
|------|----------|----------|
| 同影片 + 同畫質再次提交 | ✅ 命中，全部跳過 | （不會到達翻譯步驟） |
| 同影片 + 不同畫質 | ❌ 未命中，重新處理 | ✅ 命中，翻譯跳過 |
| 不同影片 | ❌ 未命中 | ❌ 未命中 |

---

## 相關檔案

| 檔案 | 說明 |
|------|------|
| `backend/app.py` | 結果快取讀取/寫入（`process_video_task`, `save_result_to_file`）、刪除（`delete_video`）、翻譯快取檢查（翻譯區塊） |
| `storage/results/` | 結果快取 JSON 儲存目錄（含畫質，`{video_id}_{quality}.json`） |
| `storage/subtitles/` | 翻譯快取 SRT 儲存目錄（不含畫質，`{video_id}.{lang}.translated.srt`） |
