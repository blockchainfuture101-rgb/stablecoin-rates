# 📊 穩定幣理財年化率比較

各大 CEX 交易所穩定幣 Earn 產品彙整，每 2 小時自動更新。

---

## 🚀 部署步驟（一次設定，永久自動更新）

### 第一步：建立 GitHub Repo

1. 登入 [github.com](https://github.com)
2. 點右上角 **+** → **New repository**
3. 填入 Repository name（例如 `stablecoin-rates`）
4. 選 **Public**（GitHub Pages 免費版需要 Public）
5. 點 **Create repository**

---

### 第二步：上傳這些檔案

把以下所有檔案上傳到你的 repo（保持相同的資料夾結構）：

```
stablecoin-rates/
├── index.html
├── requirements.txt
├── data/
│   └── rates.json
├── scripts/
│   └── fetch_rates.py
└── .github/
    └── workflows/
        └── update-rates.yml
```

> **上傳方式：** 在 GitHub repo 頁面點 **Add file → Upload files**，然後把整個資料夾拖進去

---

### 第三步：開啟 GitHub Pages

1. 進入你的 repo → 點上方 **Settings**
2. 左側選單找到 **Pages**
3. **Source** 選 `Deploy from a branch`
4. **Branch** 選 `main`，資料夾選 `/ (root)`
5. 點 **Save**

等 1-2 分鐘後，頁面網址會出現在 Settings → Pages 最上方，格式為：

```
https://你的GitHub帳號.github.io/stablecoin-rates/
```

把這個網址傳給你的主管即可 ✅

---

### 第四步：手動觸發第一次更新

剛部署完，`data/rates.json` 是空的，需要手動跑一次抓取：

1. 進入 repo → 點上方 **Actions** 分頁
2. 左側選 **更新交易所利率**
3. 點右側 **Run workflow** → **Run workflow**
4. 等 1-2 分鐘跑完，重新整理你的頁面就有資料了

---

## ⏱ 自動更新說明

GitHub Actions 已設定 `cron: '0 */2 * * *'`，即：
- 每天 00:00 / 02:00 / 04:00 / 06:00 ... (UTC 時間) 自動執行
- 換算台灣時間：每天 08:00 / 10:00 / 12:00 ... 更新

> 注意：GitHub 免費版 cron 有時會延遲 15-30 分鐘，屬正常現象

---

## 🔧 手動新增或移除交易所

開啟 `scripts/fetch_rates.py`：

- **新增交易所**：仿照現有的 `fetch_xxx()` 函式，加入對應 API 邏輯，然後在 `main()` 的 `fetchers` 字典中加一行
- **MEXC 單獨修改**：直接改 `fetch_mexc()` 函式

---

## 📁 檔案說明

| 檔案 | 用途 |
|------|------|
| `index.html` | 前端展示頁面，主管看的就是這個 |
| `scripts/fetch_rates.py` | 抓各交易所 API，輸出 rates.json |
| `data/rates.json` | 最新利率資料（由 GitHub Actions 自動更新） |
| `.github/workflows/update-rates.yml` | 定時任務設定 |
| `requirements.txt` | Python 套件清單 |

---

## ⚠️ 注意事項

- 所有利率資料僅供**內部競品研究參考**
- 若某交易所 API 變更，該欄位會顯示為空，需要手動更新對應 `fetch_xxx()` 函式
- 建議定期觀察 GitHub Actions 的執行 log，確認各交易所資料正常抓取
