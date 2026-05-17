# yt-dlp 下載錯誤分析

## 問題描述
從伺服器日誌可看到兩個關鍵訊息：

1. `WARNING: [youtube] ... YouTube is forcing SABR streaming for this client`，表示 YouTube 已改用 **SABR (Segmented Adaptive‑Bitrate) 影片流**，而目前安裝的 `yt-dlp==2025.10.14` 無法取得這些格式的實際下載 URL，導致之後的影片請求只剩下缺少簽名的連結。
2. `ERROR: unable to download video data: HTTP Error 403: Forbidden`，在嘗試下載缺少 URL 的格式時，YouTube 回傳 403，最終拋出 `DownloadError`。

簡而言之：**YouTube 的播放格式變更（SABR）超出目前 yt‑dlp 版本的支援範圍**，即使 `format` 參數正確（`best[height<=720]` 會挑選到被 SABR 強制的格式），最終仍拿不到可下載的 URL，導致 403 失敗。

另外，日誌中還出現 `Deprecated Feature: Support for Python version 3.9 has been deprecated`，未來若 yt‑dlp 在新版本中依賴 3.10+ 的語法，可能會出現相容性問題。

## 解決方案
| 步驟 | 操作 | 為什麼<br/>(說明) |
|------|------|-------------------|
| **1️⃣ 更新 yt‑dlp** | ```bash\nuv add -U yt-dlp   # 或 pip install -U yt-dlp\n```<br>確保安裝的是 **最新的發行版**（截至 2026‑05‑17 已是 `2025.12.x` 或 `2026.02.x`），新版已加入 **SABR 流支援**，能解析出正確的分段 URL，避免 403。 | 新版會解析 YouTube 產生的 `sabr` 片段 URL，產生有效的下載連結。 |
| **2️⃣ 升級 Python** (可選) | ```bash\nuv python install 3.11\nuv sync   # 重新安裝依賴\n``` | 移除「Python 3.9 已棄用」的警告，確保未來 yt‑dlp 與其他套件不因語法差異而失效。 |
| **3️⃣ 手動指定保守的 format** (若仍失敗) | 在 `backend/services/youtube.py` `download_video` 的 `ydl_opts` 改為：```python\n'format': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]',\n``` | 讓 yt‑dlp 優先挑選單一合併檔（mp4），避免需要分段或 DASH 的 Web‑client 格式。 |
| **4️⃣ 加上 `geo_bypass` / cookies** (若影片受區域或年齡限制) | 在 `ydl_opts` 中加入：```python\n'geo_bypass': True,\n# 'cookies': str(Path('../cookies.txt'))\n``` | 某些影片僅在特定區域可下載或需要登入，`geo_bypass` 會自動繞過區域限制，cookies 則可取得已登入的授權。 |

## 實作範例 (只需調整 `download_video` 的 `ydl_opts`)
```python
ydl_opts = {
    # 若已升級到支援 SABR 的 yt‑dlp，原本的 format 可以保留。
    # 若需要保守做法，可改成以下設定：
    'format': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]',
    'outtmpl': str(output_path),
    'quiet': False,
    'no_warnings': True,
    'progress_hooks': [progress_hook],
    # 針對區域或年齡限制的影片
    'geo_bypass': True,
    # 若有登入 cookies，可取消註解以下行
    # 'cookies': str(Path('../cookies.txt')),
}
```

**後續驗證**
1. 完成 `uv add -U yt-dlp` 後重新啟動後端 (`uv run uvicorn ...`)。
2. 用相同影片 (`-I44R13iLAU`) 再次呼叫 `/api/video/process`。
3. 若仍回傳 403，檢查是否已套用 **手動 format** 或 `geo_bypass`，或改用不受限制的測試影片（例如 `https://www.youtube.com/watch?v=dQw4w9WgXcQ`）。
4. 成功產生 `storage/videos/<video_id>.mp4` 表示問題已解決。

---
*以上為對錯誤原因的分析、解決方案與程式碼範例，已保存於此文件供後續升級 Python 3.11 時參考。*