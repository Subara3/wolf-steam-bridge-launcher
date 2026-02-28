# Steam Bridge Launcher (WOLF RPG Editor)

WOLF本体にSteamworksを直接組み込まず、外部ランチャー(EXE)でSteam実績・統計を処理するブリッジです。

## 方式
- `SteamBridgeLauncher.exe`（またはGUI版）を Steam の起動EXEに設定
- ランチャーが `Game.exe` を起動
- WOLF側が `steam_cmd/*.txt` にコマンドを吐く
- ランチャーがコマンドを読み、Steam API を実行

## 必要物
- Steamworks SDK
- Visual Studio 2022 (Desktop development with C++) — C++版のみ
- Python 3.10+ — GUI版のみ
- ターゲットは **Win32 (x86)**

## フォルダ例
```
GameFolder/
  SteamBridgeLauncher.exe   (C++版) or WOLF-Steam-Bridge-GUI.exe (GUI版)
  Game.exe
  steam_api.dll
  steam_appid.txt (開発中のみ)
  steam_cmd/
```

## コマンド一覧

`steam_cmd/` 内のテキストファイルに1行で記述。ファイル名は任意（例: `cmd_001.txt`）。

| コマンド | 書式 | 説明 |
|----------|------|------|
| `unlock` | `unlock ACH_ID` | 実績を解除 |
| `clear` | `clear ACH_ID` | 実績をリセット（デバッグ用） |
| `clear_all` | `clear_all` | 全実績をリセット（デバッグ用） |
| `set_stat` | `set_stat STAT_NAME int\|float VALUE` | Stat値を設定 |
| `get_stat` | `get_stat STAT_NAME int\|float` | Stat値を取得（ログに出力） |

### コマンド例
```
unlock ACH_CLEAR_STAGE_1
```
```
clear ACH_CLEAR_STAGE_1
```
```
set_stat TOTAL_KILLS int 42
```
```
get_stat PLAY_TIME float
```

## GUI版

### 機能
- **4タブ構成**: Main / Achievements / Stats / Log
- **設定保存**: Game EXE パス・コマンドディレクトリ・ドライラン設定を `steam_bridge_config.json` に自動保存
- **Game.exe 自動検出**: exe と同じフォルダの `Game.exe` を起動時に自動設定
- **ドライラン**: Steam API を呼ばずにコマンド監視のみ動作（開発時テスト用）
- **実績一覧**: Achievements タブで全実績の状態表示、手動 Unlock/Clear
- **Stats 操作**: Stats タブで Int/Float 型の Stat を Get/Set
- **ログ**: 色分け表示（成功=緑、失敗=赤）、エクスポート機能
- **トースト通知**: 実績解除時に Steam 風ポップアップ
- **ドラッグ&ドロップ**: exe をウィンドウにドロップしてパス設定（`windnd` インストール時のみ）

### GUI版の起動
```bash
pip install -r requirements.txt
python steam_bridge_gui.py
```

### GUI版のビルド済みexe取得
- GitHub Actions: `build-gui-pyinstaller`
- 実行後、Artifact `WOLF-Steam-Bridge-GUI-win` から `WOLF-Steam-Bridge-GUI.exe` を取得

## ウディタ側の連携方法

WOLF RPG Editor（ウディタ）側からコマンドを送るには、**コモンイベント**でテキストファイルを書き出します。

### コモンイベント例: 実績解除

```
■ コモンイベント「Steam実績解除」
  入力: CSelf[5] = 実績ID（文字列）

  ▼ コマンドファイル名を組み立て
  ■変数操作: CSelf[0] = SysStr[実績カウンタ] (連番)
  ■文字列操作: CSelf[9] = "steam_cmd/ach_"
  ■文字列操作: CSelf[9] += CSelf[0]
  ■文字列操作: CSelf[9] += ".txt"

  ▼ ファイル書き出し
  ■文字列操作: CSelf[8] = "unlock "
  ■文字列操作: CSelf[8] += CSelf[5]
  ■パーティ画像の保存（テキスト版）: CSelf[9] にCSelf[8]を保存

  ▼ カウンタ加算（ファイル名の重複防止）
  ■変数操作: SysStr[実績カウンタ] += 1
```

### コモンイベント例: Stat設定

```
■ コモンイベント「Steam Stat設定」
  入力: CSelf[5] = Stat名, CSelf[6] = 型("int"/"float"), CSelf[7] = 値

  ■文字列操作: CSelf[8] = "set_stat "
  ■文字列操作: CSelf[8] += CSelf[5]
  ■文字列操作: CSelf[8] += " "
  ■文字列操作: CSelf[8] += CSelf[6]
  ■文字列操作: CSelf[8] += " "
  ■文字列操作: CSelf[8] += CSelf[7]

  ▼ ファイル書き出し（ファイル名は連番管理）
  ■パーティ画像の保存（テキスト版）: CSelf[9] にCSelf[8]を保存
```

> **ポイント**: ウディタの「パーティ画像の保存」コマンドはテキスト書き出しにも使えます。ファイル名を `steam_cmd/` 以下にすることで、ブリッジが自動検出・処理・削除します。

## C++版ビルド要点（ローカル）
1. 新規 C++ プロジェクト（空）
2. `SteamBridgeLauncher.cpp` を追加
3. C/C++ 追加インクルードに `steamworks_sdk/public` を設定
4. リンカ追加ライブラリに `steam_api.lib` を設定（sdk redistributable_bin/win32）
5. 構成を `Release | Win32` にしてビルド

## GitHub Actionsでビルド（手元Windows不要）
このリポジトリには `build-win32` workflow を用意済み。

1. Steamworks SDK を zip 化して base64 にする
2. リポジトリ Secret に `STEAMWORKS_SDK_ZIP_BASE64` として登録
3. Actions → `build-win32` → Run workflow
4. Artifact `SteamBridgeLauncher-win32` から exe を取得

## 注意
- 実績ID(`ACH_TEST_01`など)はSteamworks管理画面で定義済みであること
- Steamクライアント経由起動が基本
- Anti-cheat系タイトルにはこの方式を混ぜないこと
