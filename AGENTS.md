# AGENTS.md

## Overview

PySide6 と SQLite3 による 1 日スケジュール設計デスクトップアプリ。詳細は @README.md を参照。

## Commands

```bash
# リポジトリルートから起動（README 記載）
python app_day_schedule/app_day_schedule.py

# app_day_schedule ディレクトリで起動
cd app_day_schedule
python app_day_schedule.py
```

自動テストは現状未整備。改修後は該当操作の手動確認を行う。

## Testing Policy

- 不具合修正では「何が壊れていたか」を先に言語化し、再現手順と期待結果を明確にする
- 対症療法ではなく、根本原因を検知・再発防止できる観点で検証する（時刻・プロファイル・アラーム・DB は境界が出やすい）
- 完了報告前に、変更範囲に関係する確認を実行し、未実施なら未実施であることを明示する
- テストを追加する場合は、UI は `QtTest` 等で操作可能な範囲から優先し、タイマー・アラームは時刻モックや短い間隔での検証を検討する

## Project Structure

エントリポイント兼本体: `app_day_schedule.py`（単一ファイル。肥大化しているため、新規の大きな責務は別モジュール抽出を検討する）

永続化: アプリフォルダ直下の `schedule.db`（SQLite）、ウィンドウ位置は `window_app_day_schedule.txt`（ホスト名キーの CSV）

## Do

- PySide6 を使う（PyQt ではない）
- DB スキーマ・マイグレーション方針を変える場合は README と既存データとの整合を確認する
- アラーム・ポモドーロ・現在時刻まわりは、分単位・日跨ぎ・重複鳴動など README に書かれた仕様と矛盾しないか確認する

## Don't

- デフォルトプロファイルの削除・編集を許可しない（README の制約）
- 通知音まわりを無暗に握りつぶさない（失敗はログやユーザーへのフィードバックで明示する）

## Safety

許可（確認なし）: ファイル読み取り、lint、手動起動確認

事前確認: 依存パッケージの追加/削除、DB スキーマ変更、設定・ファイル形式の変更

## Known Gotchas

- 効果音は `winsound` 利用のため Windows 前提（他 OS では未対応や分岐が必要）
- スリープ/休止明けなど大きな時刻ジャンプではアラームが取りこぼす場合がある（README 記載）
- スケジュールは最大 24 時間まで（README 記載）
