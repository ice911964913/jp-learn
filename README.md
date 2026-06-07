# jp_learn

個人用日文學習 App，目標 N4 → N3 / N2。

純拉式設計：想練習的時候打開瀏覽器就好，不會主動推播。

## 功能

| 頁面 | 用途 |
|------|------|
| 📖 複習 | SM-2 間隔重複，今日到期的單字卡片式複習 |
| 📚 生字本 | 手動加字 / jisho.org 自動查 / 搜尋 / 篩選 / 刪除 |
| 📰 文章 | 貼任何日文 → 自動標 furigana（HTML ruby）→ 圈生字加入 |
| 🗞️ NHK 新聞 | 一鍵抓 NHK News Easy 最新文章，標假名閱讀 |
| 📊 進度 | 累積單字數、JLPT 等級分布、過去 30 天複習量、未來 14 天到期排程 |

## 技術棧

- **Streamlit** — UI（手機瀏覽器加入主畫面當 App 用）
- **SQLite** — 本機儲存（`data/jp_learn.db`），不進 git
- **pykakasi** — 漢字 → 平假名 標注，純 Python 無 MeCab
- **fugashi + unidic-lite** — 分詞（備用，目前 furigana 用 pykakasi 就夠）
- **jisho.org API** — 免費字典，無金鑰
- **NHK News Easy** — 真實 N3-N4 級新聞（自建爬蟲）
- **SM-2 演算法** — Anki 同款的間隔重複排程

## 安裝 + 啟動

```powershell
cd c:\Users\ice91\Python\jp_learn
python -m pip install -r requirements.txt
streamlit run app.py
```

首次啟動會自動匯入 124 個 N3 起始單字。瀏覽器自動打開 http://localhost:8501

## 手機在外面也能用（Tailscale）

1. 電腦裝 [Tailscale](https://tailscale.com/download)，登入後取得內部 IP（例：`100.x.x.x`）
2. 手機裝 Tailscale App，登入同一帳號
3. 電腦上跑 `streamlit run app.py` 保持開著
4. 手機瀏覽器開 `http://100.x.x.x:8501`
5. Safari / Chrome 選「加到主畫面」→ 變成 App 圖示

## 專案結構

```
jp_learn/
├── app.py                    # Streamlit 主程式（路由 + 5 個頁面）
├── requirements.txt
├── db/
│   └── schema.py             # SQLite schema + get_conn / init_db
├── srs/
│   └── sm2.py                # SM-2 演算法 + 排程 query
├── ingest/
│   ├── furigana.py           # pykakasi 包裝：annotate / annotate_ruby / tokenize
│   ├── jisho.py              # jisho.org API client
│   └── nhk_easy.py           # NHK News Web Easy 爬蟲
├── corpus/
│   ├── n3_starter.csv        # 124 個 N3 起始單字
│   └── seed.py               # 匯入 CSV → vocab + 建 SRS 排程
├── data/
│   └── jp_learn.db           # 本機 SQLite（.gitignore）
└── .streamlit/
    └── config.toml
```

## SM-2 評分對應

複習時的 4 個按鈕對應 SM-2 quality 分數：

| 按鈕 | quality | 意義 | 下次到期 |
|------|---------|------|----------|
| 😵 忘記 | 0 | 完全沒印象 | 重置：明天 |
| 😅 模糊 | 2 | 想很久才出來 | 重置：明天 |
| 🤔 想到 | 4 | 想了一下答對 | 拉長 |
| ⚡ 秒懂 | 5 | 瞬間反應 | 大幅拉長 |

quality < 3 視為失敗，repetitions 歸零、interval 重置成 1 天。

## 之後想做

- [ ] N2 詞表匯入（目前只有 N3 starter）
- [ ] 文法句型表（`grammar` table 已建好，待填內容）
- [ ] 文章閱讀時點字直接彈出 jisho（目前要打字輸入）
- [ ] 朝日 / Yahoo Japan 新聞 ingest（N2 程度）
- [ ] 雙語對照模式（日 / 中 切換）
