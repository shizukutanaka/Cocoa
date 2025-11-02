# コードフルチェックガイド

## 0. 基本情報

- **目的**
  - プロジェクト全体の品質を体系的に確認するための標準手順を提供します。
- **適用範囲**
  - `main/` 以下のプロダクションコード
  - `tests/` 以下の自動化テスト
  - `docs/` 以下の技術文書
- **記録項目**
  - **日付**: YYYY年MM月DD日
  - **ファイル名**: 対象ファイルまたはモジュール
  - **言語**: 使用言語（例: Python, TypeScript）
  - **チェック者**: 担当者氏名またはID

---

## 1. 構造と設計

- **単一責任原則**
  - 各関数・クラスが単一の目的に限定されているかを確認します。
- **ネスト構造**
  - 制御フローのネストが3階層以内に収まっているかを確認します。
- **依存関係**
  - 循環依存の有無を調査し、検出した場合は依存構造を再設計します。
- **命名規則**
  - 変数は意図を示す明確な名前か。
  - 関数名は動詞で始まっているか。
  - 定数は大文字とアンダースコアで表記されているか。
  - マジックナンバーが定数化されているか。

## 2. コードの品質

- **意図の明確化**
  - コードが自己文書化されているか。
  - コメントは複雑なロジックの補助に限定されているか。
- **複雑さの抑制**
  - 早期リターンを適用し、ネストと条件分岐を削減しているか。
- **重複排除**
  - 冗長なコードを関数化または共通化しているか。
- **未使用要素**
  - 未使用の変数、関数、importを削除しているか。
- **関数の規模**
  - 関数長は概ね20行以内か。
  - 引数数は概ね3つ以内か。
  - 副作用の有無が明示されているか。

## 3. エラー処理と安定性

- **エラーハンドリング**
  - 例外が発生し得る箇所に適切なtry-exceptやガード条件を設けているか。
- **メッセージ品質**
  - エラーメッセージが利用者にとって実用的か。
- **入力検証**
  - nullや空文字列、空配列などの境界条件を処理しているか。
- **境界ケース**
  - 最大値、最小値、オフバイワン、ゼロ除算などのケースを網羅しているか。

## 4. パフォーマンス

- **計算量**
  - 必要以上に高い計算量（O(n^2)など）がないかを確認します。
- **無駄な処理**
  - 不要なループや再計算を排除しているか。
- **データ構造**
  - 要件に適したデータ構造を採用しているか。
- **早期終了とキャッシュ**
  - 早期終了が有効な箇所で適用されているか。
  - 高負荷処理でキャッシュや遅延評価を検討しているか。

## 5. セキュリティ

- **入力検証**
  - 外部入力に対する検証が行われているか。
- **典型的な脅威対策**
  - SQLインジェクション、XSS、パストラバーサルへの対策が実装されているか。
- **情報管理**
  - 機密情報をログ出力していないか。
  - 認証情報がハードコードされていないか。
- **権限と暗号化**
  - 適切な権限チェックが存在するか。
  - 暗号化が必要なデータを適切に保護しているか。

## 6. テスト

- **網羅性**
  - 主要機能、エッジケース、エラーケースを対象とするテストが存在するか。
- **実行可能性**
  - テストが独立して実行可能か。
  - モックやスタブを適切に使用しているか。
- **性能**
  - テストが短時間で完了するか。
- **命名**
  - テスト名が意図を明確に示しているか。

## 7. 依存関係と互換性

- **依存管理**
  - 不要な依存を削除しているか。
  - バージョンを固定しているか。
- **脆弱性**
  - 既知の脆弱性を含む依存がないか。
- **ライセンスと環境**
  - ライセンスの互換性を確認しているか。
  - ターゲット環境（ブラウザ、Node.js、OSなど）で動作するか。
  - 後方互換性が維持されているか。

## 8. ドキュメント

- **APIとインターフェース**
  - 公開APIや公開関数に説明が存在するか。
  - 型定義やインターフェースが明確か。
- **使用例**
  - 適切な使用例が用意されているか。
- **READMEと履歴**
  - `README.md` が最新状態か。
  - TODOコメントが管理されているか。
  - 変更履歴とデプロイ手順が明記されているか。

## 9. 統合と動作確認

- **統合テスト**
  - 実環境または近似環境で動作を確認しているか。
- **エンドツーエンド**
  - エンドツーエンドテストやパフォーマンステストを実施しているか。
- **品質ゲート**
  - Linterが成功しているか。
  - ビルドが成功しているか。
  - 全テストが合格しているか。
  - コードレビューが完了しているか。

## 10. クリーンアップ

- **不要物削除**
  - デッドコード、デバッグコード、`console.log` などの一時ログが除去されているか。
- **ファイル整理**
  - 重複ファイルや未使用ファイルを削除しているか。
  - ファイル名とディレクトリ構造が論理的か。

---

## チェック結果サマリー

- **チェック項目総数**: 10
- **完了項目数**: 例) 8
- **要対応項目数**: 例) 2
- **主な問題点**
  - **[問題1]**: 概要記述
  - **[問題2]**: 概要記述
- **次のアクション**
  - **[対応1]**: 担当者と期限
  - **[対応2]**: 担当者と期限
- **備考**
  - 追加情報や参考資料を記載します。

## クイックチェック（5分）

- **動作確認**: 基本機能が期待どおりに動作するか。
- **エラー処理**: 代表的なエラーが適切に処理されるか。
- **命名**: 主要な識別子の命名が明確か。
- **重複**: 目立つ重複コードがないか。
- **テスト**: 主要テストが存在し、すぐに実行できるか。
- **セキュリティ**: 危険な入力経路が放置されていないか。
- **ドキュメント**: `README.md` と関連ドキュメントが最新か。

## チェック完了記録

- **完了日時**: YYYY年MM月DD日 HH:MM
- **確認者署名**: 氏名または電子署名

---

# Code Full Check Guide

## 0. Basic Information

- **Purpose**
  - Provide a standardized procedure for validating overall project quality.
- **Scope**
  - Production code under `main/`
  - Automated tests under `tests/`
  - Technical documentation under `docs/`
- **Record Fields**
  - **Date**: YYYY-MM-DD
  - **File Name**: Target file or module
  - **Language**: Programming language in use (for example: Python, TypeScript)
  - **Reviewer**: Name or identifier of the checker

---

## 1. Structure and Design

- **Single Responsibility**
  - Confirm that each function and class has a single, clear responsibility.
- **Nesting Depth**
  - Ensure control flow nesting stays within three levels.
- **Dependencies**
  - Detect cycles and redesign the dependency graph if needed.
- **Naming Conventions**
  - Variables clearly express their intent.
  - Function names begin with verbs.
  - Constants use uppercase with underscores.
  - Magic numbers are extracted into constants.

## 2. Code Quality

- **Intent Clarity**
  - Code is self-explanatory where possible.
  - Comments supplement only complex logic.
- **Complexity Control**
  - Use early returns to reduce nesting and branching.
- **Duplication Removal**
  - Refactor redundant code into shared utilities.
- **Unused Elements**
  - Remove unused variables, functions, and imports.
- **Function Size**
  - Functions stay around 20 lines or fewer.
  - Argument counts stay around three or fewer.
  - Side effects are explicit and documented.

## 3. Error Handling and Stability

- **Exception Management**
  - Guard failure-prone areas with try-except blocks or validation checks.
- **Message Quality**
  - Error messages are actionable for operators and users.
- **Input Validation**
  - Handle null, empty strings, and empty collections.
- **Boundary Coverage**
  - Cover maximums, minimums, off-by-one, and division-by-zero scenarios.

## 4. Performance

- **Time Complexity**
  - Avoid unnecessarily high complexity (for example O(n^2)).
- **Redundant Work**
  - Remove unused loops and repeated computations.
- **Data Structures**
  - Select structures appropriate for workload and constraints.
- **Early Exit and Caching**
  - Apply early exits when feasible.
  - Consider caching or lazy evaluation for heavy operations.

## 5. Security

- **Input Validation**
  - Sanitize and validate all external inputs.
- **Threat Mitigation**
  - Guard against SQL injection, XSS, and path traversal.
- **Information Handling**
  - Prevent leaks of secrets or credentials in logs.
  - Eliminate hardcoded authentication data.
- **Authorization and Encryption**
  - Enforce proper authorization checks.
  - Protect sensitive data with appropriate encryption.

## 6. Testing

- **Coverage**
  - Ensure tests cover core features, edge cases, and failure paths.
- **Executability**
  - Tests run independently and complete without manual setup.
  - Use mocks and stubs appropriately.
- **Performance**
  - Keep tests fast and repeatable.
- **Naming**
  - Test names communicate behavior under test.

## 7. Dependencies and Compatibility

- **Dependency Hygiene**
  - Remove unnecessary packages and pin versions.
- **Vulnerabilities**
  - Verify that dependencies are free of known vulnerabilities.
- **Licensing and Environment**
  - Confirm license compatibility.
  - Validate support for target environments (browsers, Node.js, operating systems).
  - Preserve backward compatibility when changes are introduced.

## 8. Documentation

- **API and Interfaces**
  - Document public APIs and functions.
  - Describe types and interfaces clearly.
- **Usage Examples**
  - Provide representative usage samples.
- **README and History**
  - Keep `README.md` current.
  - Track TODO comments.
  - Maintain change logs and deployment procedures.

## 9. Integration and Verification

- **Integration Testing**
  - Validate behavior in production or staging-like environments.
- **End-to-End and Performance**
  - Execute end-to-end and performance tests when applicable.
- **Quality Gates**
  - Ensure linting passes.
  - Ensure builds succeed.
  - Ensure all tests pass.
  - Complete peer reviews.

## 10. Clean-up

- **Remove Temporary Code**
  - Delete dead code, debug code, and temporary logging such as `console.log`.
- **File Organization**
  - Remove duplicate or unused files.
  - Keep file names and directories logical and consistent.

---

## Check Result Summary

- **Total Checklist Items**: 10
- **Completed Items**: Example) 8
- **Items Requiring Action**: Example) 2
- **Key Issues**
  - **[Issue 1]**: Outline
  - **[Issue 2]**: Outline
- **Next Actions**
  - **[Action 1]**: Assignee and due date
  - **[Action 2]**: Assignee and due date
- **Remarks**
  - Record supplemental notes and references.

## Quick Check (5 minutes)

- **Functionality**: Verify core behavior works as expected.
- **Error Handling**: Confirm common failures are managed safely.
- **Naming**: Ensure major identifiers remain meaningful.
- **Duplication**: Scan for obvious duplicate code.
- **Testing**: Confirm essential tests exist and can be executed promptly.
- **Security**: Look for unguarded input channels.
- **Documentation**: Verify `README.md` and related guides are current.

## Completion Log

- **Completion Timestamp**: YYYY-MM-DD HH:MM
- **Reviewer Signature**: Name or electronic signature
