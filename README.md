# 1日のスケジュール設計アプリ

![image](https://github.com/user-attachments/assets/2e379331-7442-42d6-b10c-2ff0f59c1973)


## 概要
このアプリケーションは、1日のスケジュールを視覚的に管理・設計するためのツール。24時間のタイムラインに沿ってスケジュールを配置し、現在の進行状況をリアルタイムで確認可能。

## 主な機能
- 24時間タイムラインでのスケジュール表示
- 30分単位でのスケジュール登録
- 複数のプロファイル管理
- スケジュールの色分け
- リアルタイムでの進行状況表示
- スケジュールの追加・編集・削除
- ウィンドウ位置の記憶

## 技術仕様
- 開発言語: Python
- GUIフレームワーク: PySide6 (Qt)
- データベース: SQLite3

## 使用方法
1. 起動すると24時間のタイムラインが表示される
2. 「スケジュール追加」から新規スケジュールを登録する
   - 予定名、開始/終了時刻、色を設定
   - 時刻は30分単位
3. 登録済みスケジュールはリストに表示される
4. ダブルクリックで編集できる
5. プロファイルで複数のスケジュールパターンを管理する
   - 「プロファイル管理」から新規作成
   - 画面上部で切り替え

## 機能
- リアルタイム進行表示：現在時刻を赤線で表示
- 進行状況表示：経過時間と残り時間を表示
- カラー管理：スケジュールごとに色分け
- ウィンドウ位置記憶：前回位置を保存
- 基準時刻設定：表示開始時刻の変更
- プロファイル管理：追加・編集・削除が可能（デフォルトプロファイルを除く）

## 注意点
- スケジュールは最大24時間まで
- データはSQLiteデータベースに保存
- アプリケーションフォルダの書き込み権限が必要
- プロファイル削除時は紐づくスケジュールも削除
- デフォルトプロファイルは削除不可
