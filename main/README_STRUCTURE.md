# Cocoa フォルダ構造

## プロジェクト構成

```
Cocoa/
├── setup/                # セットアップ関連ファイル
│   ├── setup.bat        # Windows用セットアップスクリプト
│   ├── setup.sh         # macOS用セットアップスクリプト
│   ├── requirements.txt # 依存パッケージリスト
│   └── README.md       # セットアップ手順書
│
├── launch/              # 起動関連ファイル
│   ├── run_cocoa.bat   # Windows用起動スクリプト
│   ├── run_cocoa.sh    # macOS用起動スクリプト
│   ├── backup_cocoa.bat # Windows用バックアップスクリプト
│   └── backup_cocoa.sh  # macOS用バックアップスクリプト
│
└── main/               # メインソースコード
    ├── *.py           # Pythonソースファイル
    ├── *.json         # 設定ファイル
    ├── locales/       # 多言語対応ファイル
    └── __pycache__/   # コンパイル済みPythonファイル
```

## セットアップ手順

1. `setup` フォルダに移動
2. Windows: `setup.bat` をダブルクリック
3. macOS: ターミナルで `./setup.sh` を実行

## 起動手順

1. `launch` フォルダに移動
2. Windows: `run_cocoa.bat` をダブルクリック
3. macOS: ターミナルで `./run_cocoa.sh` を実行

## バックアップ手順

1. `launch` フォルダに移動
2. Windows: `backup_cocoa.bat` をダブルクリック
3. macOS: ターミナルで `./backup_cocoa.sh` を実行

## 注意事項

- セットアップスクリプトを実行する前に、必要な権限があることを確認してください
- 起動スクリプトは仮想環境が存在する場合に自動的に有効化します
- バックアップスクリプトは自動的に設定ファイルとデータをバックアップします
