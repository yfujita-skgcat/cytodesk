
# Compensation
- Analysis -> "Compensation Workspace" と Analysis -> "Compensation Controls (Workspace)" の両方が同じようなダイアログを表示しているように見える。
- Analysis -> "Compensation Workspace" で開かれるダイアログが大きすぎてモニタに収まらない場合がある。
- そのダイアログControls Calculate と "Matrix Preview" があるが両方とも必要な機能か?
- Matrix Preview タブの Samples のプルダウンに表示されるサンプル名がサンプルIDでユーザーにはわかりにくい。サンプル名を表示するようにしてほしい。
- Matrix Preview タブのGUIレイアウトわかりにくい。Bindings はMatrix Preview タブにある必要がないので、別のタブに移動するか、Matrix Preview タブから削除してほしい。
- Bindings があった場所に、Matrix ID, Name, Source, Notes, Channels, Select all Channel button, Clear all Channel Button, Matrix Heat Map Preview を移動して、右側のエリアは主にドットプロットのプレビューを表示するようにして、プロットプレビューの全体像が見えるようにしてください。

# gating
- create gate で rectangle を作成(名前を beads にする). -> create gate でboolean gate を作成。gate name をnot beads にして作成. -> 作成した後にgateの編集(例えばnot からor に変更など)ができない。

# パッケージ起動時の GTK/GLib/GIO 警告
- GitHub からダウンロードした PyInstaller 版 GUI を起動すると、`libgvfs*`、`libibus`、`libdconfsettings` のロード時に `undefined symbol` が表示されることがある。
- 代表的なメッセージは `g_task_set_static_name`、`g_assertion_message_cmpint` の未解決、および `Loading IM context type 'ibus' failed` である。
- 原因は、配布物に含まれる GLib/GIO とホスト OS の GTK/GIO プラグイン（GVFS、IBus、dconf など）の ABI またはライブラリ探索順が一致しない、環境依存の問題と考えられる。Flowdesk/CytoDesk の FCS解析・プロット・ゲート・統計計算そのもののエラーではない。
- GUI が起動して通常のローカル FCS 操作を行える場合、通常の解析結果には直接影響しない。ただし、日本語入力（IBus）、ネットワーク/リモートファイルの参照、GTK デスクトップ設定などが利用できない、または不安定になる可能性がある。
- 未解決の既知問題として扱い、配布版の受け入れ確認では、(1) テキスト欄への日本語入力、(2) ファイルダイアログからの FCS 追加、(3) ローカルファイルの保存、(4) 解析・プロット・ゲート・統計の実行を個別に確認する。
- 恒久的な回避策として GIO モジュールを無条件に無効化してはならない。リモートファイルやデスクトップ連携を損なう可能性があるため、今後は不要な GTK/GIO ライブラリの同梱を減らすか、同梱ライブラリとプラグインのバージョンを一貫させる方向で修正する。
- 配布版の修正完了条件は、クリーンな対応環境で起動時の `undefined symbol` 警告が出ず、上記の入力・ファイル操作・解析操作がすべて成功することである。
