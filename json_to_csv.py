import sys
import json
import csv
import os

def convert_json_to_csv(json_path):
    # ファイルの存在確認
    if not os.path.exists(json_path):
        sys.exit(f"エラー: 指定されたファイルが存在しません: {json_path}")

    # JSONファイルの読み込み
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        sys.exit(f"エラー: JSONファイルの読み込みに失敗しました: {e}")

    # commentList の抽出
    comment_list = data.get("commentList", [])

    # 出力先CSVファイル名の生成（.json を .csv に置換）
    base_path, _ = os.path.splitext(json_path)
    csv_path = f"{base_path}.csv"

    # CSVヘッダーの定義
    headers = ["publishedAt", "likeCount", "totalReplyCount", "textOriginal"]

    # CSVファイルへの書き出し
    try:
        with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            
            # ヘッダーの書き込み
            writer.writerow(headers)
            
            # 各コメントデータの書き込み
            for comment in comment_list:
                writer.writerow([
                    comment.get("publishedAt", ""),
                    comment.get("likeCount", 0),
                    comment.get("totalReplyCount", 0),
                    comment.get("textOriginal", "")
                ])
                
        print(f"変換が完了しました: {csv_path}")
        print(f"変換件数: {len(comment_list)} 件")

    except Exception as e:
        sys.exit(f"エラー: CSVファイルの書き出しに失敗しました: {e}")

def main():
    # 引数のチェック
    if len(sys.argv) != 2:
        sys.exit("使い方: python json_to_csv.py <JSONファイルのパス>")

    json_path = sys.argv[1]
    convert_json_to_csv(json_path)

if __name__ == "__main__":
    main()