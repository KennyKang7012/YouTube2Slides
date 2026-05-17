# 升級 Python 以及套件管理指南

## 1️⃣ 直接使用 **uv**（最簡單、最可靠的方式）

| 步驟 | 指令 | 說明 |
|------|------|------|
| a) 先把 `requires‑python` 版本升到 3.11 | 編輯 **`backend/pyproject.toml`** →<br>`requires-python = ">=3.11"` | 讓 uv 知道新環境的最低 Python 版本。 |
| b) 重新產生 lock 檔（如果先前沒有） | ```bash\ncd backend\nuv lock\n``` | `uv.lock` 會把所有依賴與精確版本寫入，保證未來安裝的結果一致。 |
| c) 匯出 **requirements.txt**（可選） | ```bash\nuv export -f requirements.txt -o requirements.txt\n``` | `uv export` 會根據 `uv.lock` 產生符合 **pip** 的 `requirements.txt`，內容與 lock 完全同步。<br>如果只想保留 lock，步驟 c）可以省略，直接用 uv 完成安裝即可。 |
| d) 切換到 Python 3.11（全域或使用 `uv python install`） | ```bash\nuv python install 3.11   # 產生 3.11 虛擬環境\n``` | uv 會在 `.venv`（或自訂路徑）中建立新的 3.11 虛擬環境。 |
| e) 在新環境安裝套件 | ```bash\nuv sync   # 讀取 pyproject + uv.lock 安裝所有依賴\n``` | `uv sync` 會自動從 `uv.lock` 把正確的套件版號安裝到剛建立的 3.11 虛擬環境中。 |

**優點**
- 完全由 `uv` 管理：不需要手動維護兩份依賴清單。  
- `uv.lock` 為可重現的快照，升級 Python 後只要執行 `uv sync` 即可。  
- `uv export` 提供的 `requirements.txt` 與 lock 完全一致，若你仍想使用 `pip install -r requirements.txt` 也能無縫切換。

---

## 2️⃣ 只想得到一個 **requirements.txt**（手動或自動生成）

### 方法 A – 從 `pyproject.toml` 直接產生（最直接的文字清單）

```text
fastapi>=0.104.1
uvicorn[standard]>=0.24.0
yt-dlp==2025.10.14
ffmpeg-python>=0.2.0
pillow>=10.1.0
deep-translator>=1.11.4
python-multipart>=0.0.6
aiofiles>=23.2.1
pydantic>=2.5.0
python-dotenv>=1.0.0
celery>=5.3.4
redis>=5.0.1
sqlalchemy>=2.0.23
openai>=1.12.0
anthropic>=0.18.0
google-generativeai>=0.3.0
```

把上面的文字存到 **`backend/requirements.txt`**（或專案根目錄），之後在升級後的環境執行：

```bash
uv pip install -r backend/requirements.txt
```

> 這個檔案只包含 `pyproject.toml` 中列出的依賴，若未來有新增或變更，記得同步更新 `requirements.txt`。

### 方法 B – 用 **uv pip freeze** 產出已安裝的精確版本

```bash
cd backend
uv pip freeze > requirements.txt
```

`requirements.txt` 會列出目前 **.venv** 中實際安裝的套件與版本（例如 `fastapi==0.104.2`），在升級 Python 後只要執行：

```bash
uv pip install -r requirements.txt
```

**注意**：此方式依賴目前的虛擬環境；若在升級前先跑 `uv pip freeze`，就能保留完整的版本資訊。

---

## 3️⃣ 建議流程（結合上述兩種方式）
1. **先更新 `pyproject.toml`**（把 `requires-python` 改成 `>=3.11`）。
2. 在 **升級前**，使用 `uv export -f requirements.txt -o requirements.txt` 產出一份與 lock 同步的 `requirements.txt`（作為備份）。
3. 直接 **切換 Python 3.11**： `uv python install 3.11 && uv sync`。  
   - 若你偏好使用 `pip`，只要跑 `uv pip install -r requirements.txt` 即可。
4. 測試應用（ `uv run uvicorn app:app --reload` ）確定所有套件在 3.11 下正常。

---

## 小結
- **最推薦**：保留 `uv.lock`，升級後只跑 `uv sync`。
- **如果一定要 `requirements.txt`**：`uv export -f requirements.txt -o requirements.txt`（自動從 lock 產生）或手動把 `pyproject.toml` 的 `dependencies` 複製成上面的文字清單。
- **升級 Python**：在 `pyproject.toml` 裡調整 `requires-python`，然後執行 `uv python install 3.11 && uv sync`（或 `uv pip install -r requirements.txt`）即可。

祝升級順利，若有其他依賴衝突或安裝問題隨時再告訴我！