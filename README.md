# Chotto Voice 🎤

Windows / macOS 向け音声入力アシスタント - Aqua Voiceの代替アプリケーション

## 機能

- 🎤 音声録音・テキスト変換（Whisper：ローカル / OpenAI API）
- 🤖 AI整形（業界標準プロバイダから選択）
  - Google Gemini / Anthropic Claude / OpenAI
  - Ollama / LM Studio（ローカル、APIキー認証にも対応）
  - 任意のOpenAI互換エンドポイント（base_url + APIキー + モデル指定）
- ✍️ 整形結果をストリームしながらフォーカス中のテキストボックスへ入力
- 📍 インジケーターをフォーカス中のテキストボックス周辺にフロート（取得不可時は画面隅）
- 🍎 Mac風のインターフェース
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

## ビルド（exe / app）

GitHub Actions（`.github/workflows/build.yml`）が Windows の `.exe` と macOS の `.app` を
自動ビルドします（`claude/**` ブランチへの push / タグ `v*` / 手動実行）。成果物は
Actions のアーティファクトから取得できます。

ローカルでビルドする場合:

```bash
# Windows
build.bat            # dist\ChottoVoice.exe を生成

# macOS
./build_mac.sh       # dist/ChottoVoice.app を生成
```

> 注: PyInstaller はクロスコンパイルできないため、Windows の `.exe` は Windows 上で、
> macOS の `.app` は macOS 上でビルドする必要があります（CI が両方を担当）。

## ロードマップ

- [x] Phase 1: 基本機能
  - [x] 音声録音
  - [x] Whisper API連携
  - [x] Claude/GPT API連携
  - [x] 基本GUI

- [x] Phase 2: UX改善
  - [x] ホットキー対応
  - [x] 設定画面
  - [x] Mac風UI
  - [x] フォーカス追従インジケーター
  - [x] ストリーム入力

- [x] Phase 3: 拡張
  - [x] Ollama対応
  - [x] LM Studio対応
  - [x] 汎用OpenAI互換対応
  - [x] ローカルWhisper対応
  - [x] Windows exe化 / macOS app化

## ライセンス

MIT License

---

Made with ❤️ by びびはる
