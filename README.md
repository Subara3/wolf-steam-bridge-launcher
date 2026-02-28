# Steam Bridge Launcher (WOLF RPG Editor)

WOLF本体にSteamworksを直接組み込まず、外部ランチャー(EXE)でSteam実績を処理する最小サンプルです。

## 方式
- `SteamBridgeLauncher.exe` を Steam の起動EXEに設定
- ランチャーが `Game.exe` を起動
- WOLF側が `steam_cmd/*.txt` にコマンドを吐く
- ランチャーがコマンドを読み、`SetAchievement` + `StoreStats` を実行

## 必要物
- Steamworks SDK
- Visual Studio 2022 (Desktop development with C++)
- ターゲットは **Win32 (x86)**

## フォルダ例
```
GameFolder/
  SteamBridgeLauncher.exe
  Game.exe
  steam_api.dll
  steam_appid.txt (開発中のみ)
  steam_cmd/
```

## WOLF側のコマンド例
`steam_cmd/cmd_001.txt` の中身:
```
unlock ACH_TEST_01
```

## ビルド要点（ローカル）
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
