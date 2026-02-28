# ウディタ × Steam 実績 かんたん手引き

**「自分のウディタ作品を Steam で出したい。実績もつけたい。でもプログラミングはできない」**
――そんな人のためのガイドです。

この手引きでは **WOLF Steam Bridge GUI** を使って、ウディタ製ゲームに Steam 実績と統計（Stat）を組み込む方法を、ゼロから説明します。

---

## 目次

1. [しくみの概要](#1-しくみの概要)
2. [準備するもの](#2-準備するもの)
3. [Steamworks で実績を登録する](#3-steamworks-で実績を登録する)
4. [ファイルを配置する](#4-ファイルを配置する)
5. [ウディタ側の設定（コモンイベント）](#5-ウディタ側の設定コモンイベント)
6. [テストする（ドライランモード）](#6-テストするドライランモード)
7. [Steam を通して実テストする](#7-steam-を通して実テストする)
8. [リリース時のチェックリスト](#8-リリース時のチェックリスト)
9. [GUI の各タブの使い方](#9-gui-の各タブの使い方)
10. [よくある質問・トラブル](#10-よくある質問トラブル)

---

## 1. しくみの概要

ウディタは C++ や DLL を直接呼べません。
そこで **「テキストファイルを介してやり取りする」** という方法を使います。

```
  Game.exe (ウディタ製ゲーム)
       |
       |  steam_cmd/ にテキストファイルを書き出し
       v
  WOLF-Steam-Bridge-GUI.exe
       |
       |  Steam API で実績解除・統計記録
       v
     Steam
```

1. ウディタが `steam_cmd/` フォルダにテキストファイルを置く
2. Bridge GUI がそのファイルを見つけて中身を読む
3. 書かれた内容に従って Steam の実績を解除したり統計を記録する
4. テキストファイルは処理後に自動削除される

**ウディタ側ではテキストファイルを1つ書き出すだけ。** プログラミングの知識は不要です。

---

## 2. 準備するもの

| 必要なもの | 入手先 | 備考 |
|-----------|--------|------|
| Steam に登録済みのアプリ（App ID） | [Steamworks](https://partner.steampowered.com/) | Steam Direct 登録料が必要 |
| `steam_api.dll` | Steamworks SDK の `redistributable_bin/win32/` | **32bit版 (win32)** を使うこと |
| `WOLF-Steam-Bridge-GUI.exe` | 下記「ダウンロード方法」参照 | |
| ウディタ製のゲーム一式 | あなたの作品 | `Game.exe` がある状態 |

### WOLF-Steam-Bridge-GUI.exe のダウンロード方法

1. GitHub の [wolf-steam-bridge-launcher](https://github.com/Subara3/wolf-steam-bridge-launcher) を開く
2. 上部の **「Actions」** タブをクリック
3. 左メニューの **「build-gui-pyinstaller」** をクリック
4. 一番上（最新）のワークフロー実行結果をクリック
5. ページ下部の **Artifacts** セクションにある **WOLF-Steam-Bridge-GUI-win** をクリックしてダウンロード
6. zip を展開すると `WOLF-Steam-Bridge-GUI.exe` が入っている

---

## 3. Steamworks で実績を登録する

Bridge が実績を解除するには、あらかじめ Steamworks 管理画面で実績を定義しておく必要があります。

1. [Steamworks](https://partner.steampowered.com/) にログイン
2. あなたのアプリを選択
3. **「データ＆実績」→「実績」** を開く
4. 「新しい実績」をクリックして追加する

各実績に設定する項目:

| 項目 | 例 | 説明 |
|------|-----|------|
| **API Name** | `ACH_CLEAR_STAGE_1` | ウディタ側で指定する名前。**半角英数とアンダースコアだけ** |
| 表示名 | ステージ1クリア | プレイヤーに見える名前 |
| 説明 | ステージ1をクリアした | プレイヤーに見える説明文 |
| アイコン | (画像) | 解除前・解除後の2枚。64x64 推奨 |

5. 設定が終わったら **「公開」** を押す（テスト環境にも公開が必要です）

> **大事:** ここで決めた **API Name**（例: `ACH_CLEAR_STAGE_1`）を後でウディタ側で使います。メモしておいてください。

### 統計（Stat）を使いたい場合

「プレイ時間」「倒した敵の数」などを記録したい場合は、**「データ＆実績」→「統計」** で Stat も登録します。

| 項目 | 例 | 説明 |
|------|-----|------|
| **API Name** | `TOTAL_KILLS` | ウディタ側で指定する名前 |
| 種類 | INT（整数） or FLOAT（小数） | 用途に応じて選ぶ |

---

## 4. ファイルを配置する

ゲームの完成フォルダを以下の構成にします:

```
あなたのゲームフォルダ/
├── WOLF-Steam-Bridge-GUI.exe    ← ダウンロードしたもの
├── Game.exe                      ← ウディタのゲーム本体
├── steam_api.dll                 ← Steamworks SDK から取得（win32版）
├── steam_appid.txt               ← 開発テスト時のみ必要
├── Data/                         ← ウディタのデータフォルダ
└── (steam_cmd/)                  ← 自動作成されるので手動作成不要
```

### steam_appid.txt について

開発中（Steamクライアントを経由せず直接テストする場合）にだけ必要です。
中身は **App ID の数字だけ** を1行書きます:

```
480
```

（`480` は Steamworks のテスト用App ID "Spacewar" です。自分のアプリの ID に書き換えてください）

> **リリース時には steam_appid.txt を同梱しないでください。** Steam クライアント経由で起動する場合は不要です。

---

## 5. ウディタ側の設定（コモンイベント）

ここがいちばん大事なところです。
ウディタ側では **テキストファイルを書き出すだけ** で実績を解除できます。

### 5-1. 実績解除用コモンイベントを作る

コモンイベント名: **「Steam実績解除」**

#### 入力設定

| 番号 | 名前 | 種別 |
|------|------|------|
| コモンセルフ変数5 | 実績ID | 文字列 |

#### イベントコマンド

```
◆変数操作+: CSelf10[連番] = CSelf10[連番] + 1
◆文字列操作: CSelf9 = "steam_cmd/ach_\cself[10].txt"
◆文字列操作: CSelf8 = "unlock \cself[5]"
◆文字列の保存:  CSelf9 の場所に CSelf8 を保存
```

やっていることの説明:
1. **連番カウンタを増やす** → ファイル名が重複しないようにする
2. **ファイル名を組み立てる** → `steam_cmd/ach_1.txt` のような名前
3. **コマンド文を組み立てる** → `unlock ACH_CLEAR_STAGE_1`
4. **テキストファイルとして保存する** → Bridge が自動で拾って処理してくれる

#### マップイベントからの呼び出し例

ボス撃破後のイベントで:

```
◆コモンイベント「Steam実績解除」を呼ぶ
  CSelf5 ← "ACH_BEAT_BOSS_1"
```

これだけで、ボスを倒したときに実績 `ACH_BEAT_BOSS_1` が解除されます。

### 5-2. 全実績クリア用（デバッグ用）

テスト中に全実績をリセットしたい場合:

```
◆文字列操作: CSelf9 = "steam_cmd/reset.txt"
◆文字列操作: CSelf8 = "clear_all"
◆文字列の保存:  CSelf9 の場所に CSelf8 を保存
```

### 5-3. 統計（Stat）を更新する

コモンイベント名: **「Steam Stat設定」**

```
◆文字列操作: CSelf9 = "steam_cmd/stat_\cself[10].txt"
◆文字列操作: CSelf8 = "set_stat TOTAL_KILLS int \cself[6]"
◆文字列の保存:  CSelf9 の場所に CSelf8 を保存
```

ここで `\cself[6]` に値（例: 敵の撃破数の変数）を入れます。

### 5-4. 使えるコマンド一覧

テキストファイルの中身として書ける命令です:

| やりたいこと | テキストの中身 | 例 |
|-------------|---------------|-----|
| 実績を解除する | `unlock 実績ID` | `unlock ACH_CLEAR_STAGE_1` |
| 実績を取り消す（デバッグ用） | `clear 実績ID` | `clear ACH_CLEAR_STAGE_1` |
| 全実績を取り消す（デバッグ用） | `clear_all` | `clear_all` |
| 統計を設定する（整数） | `set_stat 名前 int 値` | `set_stat TOTAL_KILLS int 42` |
| 統計を設定する（小数） | `set_stat 名前 float 値` | `set_stat PLAY_TIME float 12.5` |
| 統計を確認する（ログに出力） | `get_stat 名前 型` | `get_stat TOTAL_KILLS int` |

---

## 6. テストする（ドライランモード）

Steam がなくても動作確認ができます。

1. `WOLF-Steam-Bridge-GUI.exe` をダブルクリックして起動
2. **「Dry Run」にチェックを入れる**
3. **「Start」** を押す
   - Game.exe は起動されません（ファイル監視だけが動きます）
4. `steam_cmd/` フォルダにテキストファイルを手で作って置く
   - 例: `steam_cmd/test.txt` の中身 → `unlock ACH_TEST_01`
5. GUI の Log タブに `[DRY RUN] unlock: ACH_TEST_01` と表示されれば成功

**ウディタのテストプレイと組み合わせる場合:**

1. Bridge GUI を起動 → Dry Run ON → Start
2. ウディタのテストプレイを起動
3. ゲーム内で実績解除イベントを起こす
4. Bridge GUI のログに反応が出るか確認する

> ドライランでは Steam 接続不要。`steam_api.dll` も不要です。コマンドファイルの書き出しが正しく動いているかの確認に使えます。

---

## 7. Steam を通して実テストする

ドライランでの動作確認が済んだら、実際に Steam 実績が解除されるかテストします。

1. ゲームフォルダに `steam_api.dll` と `steam_appid.txt` を配置
2. **Steam クライアントを起動してログインしておく**
3. `WOLF-Steam-Bridge-GUI.exe` をダブルクリック
4. Dry Run の **チェックを外す**
5. 「Start」を押す → Game.exe が起動される
6. ゲーム内で実績解除イベントを起こす
7. Steam オーバーレイに実績通知が出れば成功

### 実績の状態を確認・リセットする

- **Achievements タブ → Refresh**: 現在の全実績の状態を一覧表示
- **Achievements タブ → Clear All**: テストでつけた実績を一括リセット
- **ACH ID を入力 → Clear**: 個別に実績をリセット

---

## 8. リリース時のチェックリスト

Steam にゲームを公開するときの確認事項:

- [ ] Steamworks 管理画面で実績を **公開** している
- [ ] `WOLF-Steam-Bridge-GUI.exe` をゲームフォルダに入れた
- [ ] `steam_api.dll`（**32bit / win32 版**）をゲームフォルダに入れた
- [ ] **`steam_appid.txt` は入れていない**（リリース版には不要）
- [ ] Steamworks の **起動オプション** で `WOLF-Steam-Bridge-GUI.exe` を起動EXEに設定した
- [ ] ゲーム内の全実績イベントが正しいAPI Nameを使っている
- [ ] Dry Run チェックが外れている

### Steamworks の起動オプション設定

Steamworks 管理画面 → あなたのアプリ → **「インストール」→「一般」** で:

- **実行ファイル**: `WOLF-Steam-Bridge-GUI.exe`

こうすると Steam で「プレイ」を押したときに Bridge GUI が起動し、Bridge が Game.exe を起動する流れになります。

---

## 9. GUI の各タブの使い方

### Main タブ

| 項目 | 説明 |
|------|------|
| Game EXE | ゲーム本体のパス。同じフォルダの Game.exe は自動検出される |
| Command Dir | コマンドフォルダ。通常は `steam_cmd` のままでOK |
| Dry Run | チェックすると Steam 接続なしでテストできる |
| Start / Stop | 監視の開始・停止 |
| ミニログ | 最新5行のログを表示 |

exe をウィンドウにドラッグ&ドロップしてもパスを設定できます。

### Achievements タブ

| ボタン | 説明 |
|--------|------|
| Refresh | Steam から実績一覧を取得して表示 |
| Clear All | 全実績をリセット（確認ダイアログあり） |
| ACH ID + Unlock | 入力した ID の実績を手動で解除 |
| ACH ID + Clear | 入力した ID の実績を手動でリセット |

### Stats タブ

| 項目 | 説明 |
|------|------|
| Stat Name | Steamworks で設定した API Name |
| Type | Int（整数）か Float（小数）を選ぶ |
| Value | Set するときの値 |
| Set | 値を Steam に書き込む |
| Get | 現在の値を Steam から読み込む |

### Log タブ

| 項目 | 説明 |
|------|------|
| ログ表示 | 全ログを色分け表示（緑=成功、赤=失敗、青=ドライラン） |
| Clear Log | ログ表示をクリア |
| Export Log | ログをファイルに保存 |

---

## 10. よくある質問・トラブル

### Q. 「SteamAPI_Init failed」と出る
- **Steam クライアントが起動していない** → Steam にログインしてから再実行
- **steam_api.dll がない** → ゲームフォルダに 32bit 版を配置
- **steam_appid.txt がない**（直接起動の場合） → App ID を書いたテキストを配置

### Q. 実績が解除されない
- Steamworks 管理画面で実績を **公開** しているか確認
- API Name が完全一致しているか確認（大文字小文字も区別される）
- Log タブでエラーが出ていないか確認

### Q. Game.exe が起動しない
- Game EXE のパスが正しいか確認（Browse ボタンで選び直す）
- Dry Run にチェックが入っていないか確認

### Q. テスト中に実績をリセットしたい
- Achievements タブ → **Clear All** で一括リセット
- または `steam_cmd/` に `clear_all` と書いたテキストファイルを置く

### Q. ウディタからファイルが書き出されない
- `steam_cmd/` フォルダが Game.exe と同じ場所にあるか確認
- コモンイベントの文字列操作で **パスの先頭に `steam_cmd/`** が付いているか確認
- ウディタのテストプレイで `steam_cmd/` にファイルが作成されるか目視確認

### Q. 64bit 版の steam_api.dll を使ってしまった
- ウディタは 32bit アプリです。Steamworks SDK の `redistributable_bin/win32/steam_api.dll` を使ってください。`win64` のほうではありません。

### Q. Bridge GUI なしで C++ 版ランチャーを使いたい
- `SteamBridgeLauncher.exe`（C++版）でも同じことができます。ただし GUI はなく、`unlock` コマンドのみ対応です。詳しくは [README.md](README.md) を参照してください。
