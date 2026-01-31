# Chotto Voice 🎤

Windows向け音声入力アシスタント - Aqua Voiceの代替アプリケーション

## 機能

- 🎤 音声録音・テキスト変換（Whisper）
- 🤖 AI処理（Claude / GPT）
- 📌 システムトレイ常駐
- ⚙️ カスタマイズ可能な設定

## セットアップ

### 1. Python環境

Python 3.11以上が必要です。

```bash
# 仮想環境作成
python -m venv venv

# 有効化 (Windows)
venv\Scripts\activate

# 有効化 (macOS/Linux)
source venv/bin/activate

# 依存関係インストール
pip install -r requirements.txt
```

### 2. 設定

```bash
# 設定ファイルをコピー
cp .env.example .env

# .envを編集してAPIキーを設定
```

### 3. 実行

```bash
python main.py
```

## 使い方

### GUIモード
1. 「録音開始」ボタンをクリック
2. マイクに向かって話す
3. 「録音停止」をクリック
4. 音声認識結果が表示される
5. 「AIで処理」で整形・応答を取得

### ホットキーモード 🔥
| 操作 | 動作 |
|------|------|
| **ホールド** | 押している間だけ録音 |
| **ダブルタップ** | 録音開始 + スピーカーミュート |

デフォルトホットキー: `Ctrl+Shift+Space`

設定画面から変更可能:
- `Ctrl+Alt+V`
- `F9`
- `Win+H`
- カスタム設定

## 設定項目

| 項目 | 説明 | デフォルト |
|------|------|-----------|
| `AI_PROVIDER` | 使用するAI | `claude` |
| `WHISPER_PROVIDER` | 音声認識方式 | `openai_api` |
| `LANGUAGE` | UI言語 | `ja` |
| `START_MINIMIZED` | トレイで起動 | `false` |

## ロードマップ

- [x] Phase 1: 基本機能
  - [x] 音声録音
  - [x] Whisper API連携
  - [x] Claude/GPT API連携
  - [x] 基本GUI

- [ ] Phase 2: UX改善
  - [ ] ホットキー対応
  - [ ] 設定画面
  - [ ] 音声入力デバイス選択

- [ ] Phase 3: 拡張
  - [ ] Ollama対応
  - [ ] LM Studio対応
  - [ ] ローカルWhisper対応
  - [ ] Windows exe化

## ライセンス

MIT License

---

Made with ❤️ by びびはる
