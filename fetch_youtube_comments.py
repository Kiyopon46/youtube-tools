import os
import re
import sys
import time
import json
import argparse
from datetime import datetime, timezone
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import load_dotenv

# .env ファイルから環境変数を読み込む
load_dotenv()

# 日時フォーマットの定義
INPUT_DATETIME_FORMAT = "%Y%m%d%H%M%S"
OUTPUT_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
FILE_DATETIME_FORMAT = "%Y%m%d%H%M%S"

def parse_arguments():
    """コマンドライン引数の解析"""
    parser = argparse.ArgumentParser(description="YouTube動画のコメントを取得するツール")
    
    # URL または ID の排他指定グループ
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--url", help="YouTube動画のURL")
    group.add_argument("--id", help="YouTube動画のID (パラメータ v の値)")
    
    parser.add_argument(
        "--last-update", 
        dest="last_update",
        help="指定した日時より新しいコメントを取得 (形式: yyyyMMddHHmmss / UTC)"
    )
    
    parser.add_argument(
        "--include-replies",
        action="store_true",
        help="返信（子コメント）も取得対象に含める場合に使用"
    )

    return parser.parse_args()

def extract_video_id(url_or_id, is_id=False):
    """URLまたは文字列から動画IDを抽出"""
    if is_id:
        return url_or_id
    
    # URLから v=XXXXXXXXXX または youtu.be/XXXXXXXXXX を抽出
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'youtu\.be\/([0-9A-Za-z_-]{11})'
    ]
    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)
            
    sys.exit("エラー: 有効なYouTube動画IDまたはURLを特定できませんでした。")

def parse_utc_datetime(dt_str):
    """yyyyMMddHHmmss 形式の文字列を UTC タイムゾーン付き datetime オブジェクトに変換"""
    try:
        dt = datetime.strptime(dt_str, INPUT_DATETIME_FORMAT)
        return dt.replace(tzinfo=timezone.utc)
    except ValueError:
        sys.exit(f"エラー: 日時フォーマットが不正です。 '{INPUT_DATETIME_FORMAT}' 形式で指定してください。")

def fetch_comments(youtube, video_id, last_update_dt, include_replies):
    """YouTube API を呼び出してコメントを取得"""
    fetched_comments = []
    next_page_token = None
    stop_fetching = False

    part_param = "snippet,replies" if include_replies else "snippet"

    while True:
        try:
            # APIリクエスト構築 (最新順: order='time')
            request = youtube.commentThreads().list(
                part=part_param,
                videoId=video_id,
                order="time",
                maxResults=100,
                pageToken=next_page_token
            )
            response = request.execute()

            items = response.get("items", [])
            if not items:
                break

            for item in items:
                # トップレベルコメントの解析
                top_snippet = item["snippet"]["topLevelComment"]["snippet"]
                top_pub_at_str = top_snippet["publishedAt"]
                # APIからの返却値 (ISO 8601) を datetime に変換
                top_pub_at_dt = datetime.strptime(top_pub_at_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

                # --last-update 指定日時以下の場合は取得を終了する (新順のためこれ以降はすべて古い)
                if last_update_dt and top_pub_at_dt <= last_update_dt:
                    stop_fetching = True
                    break

                # データ格納
                comment_data = {
                    "textOriginal": top_snippet.get("textOriginal", ""),
                    "likeCount": top_snippet.get("likeCount", 0),
                    "totalReplyCount": item["snippet"].get("totalReplyCount", 0),
                    "publishedAt": top_pub_at_str,
                    "_parsed_dt": top_pub_at_dt  # ソート用の内部管理フィールド
                }
                fetched_comments.append(comment_data)

                # 返信（子コメント）の処理
                if include_replies and "replies" in item:
                    replies = item["replies"].get("comments", [])
                    for reply in replies:
                        reply_snippet = reply["snippet"]
                        reply_pub_at_str = reply_snippet["publishedAt"]
                        reply_pub_at_dt = datetime.strptime(reply_pub_at_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

                        # 返信も日時条件でフィルター
                        if last_update_dt and reply_pub_at_dt <= last_update_dt:
                            continue

                        reply_data = {
                            "textOriginal": reply_snippet.get("textOriginal", ""),
                            "likeCount": reply_snippet.get("likeCount", 0),
                            "totalReplyCount": 0,  # 子コメント自身に返信数は存在しないため0固定
                            "publishedAt": reply_pub_at_str,
                            "_parsed_dt": reply_pub_at_dt
                        }
                        fetched_comments.append(reply_data)

            if stop_fetching:
                break

            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break

            # 指定要件: ページネーション時の 5秒スリープ
            time.sleep(5)

        except HttpError as e:
            sys.exit(f"APIエラーが発生しました: {e}")

    return fetched_comments

def main():
    start_time = time.time()
    args = parse_arguments()

    # APIキー確認
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        sys.exit("エラー: 環境変数 'YOUTUBE_API_KEY' がセットされていません。.env ファイルを確認してください。")

    # 動画IDと基準日時の設定
    video_id = extract_video_id(args.url or args.id, is_id=bool(args.id))
    last_update_dt = parse_utc_datetime(args.last_update) if args.last_update else None

    # YouTube API クライアント初期化
    youtube = build("youtube", "v3", developerKey=api_key)

    # コメント取得
    comments = fetch_comments(youtube, video_id, last_update_dt, args.include_replies)

    # 実行日時（UTC）の記録
    executed_at_dt = datetime.now(timezone.utc)
    executed_at_str = executed_at_dt.strftime(OUTPUT_DATETIME_FORMAT)

    last_published_at_str = None
    last_pub_dt_for_filename = None

    if comments:
        # 投稿日時の昇順（古い順）にソート
        comments.sort(key=lambda x: x["_parsed_dt"])

        # 最新のコメント投稿日時を取得 (昇順ソートのため最後の要素)
        latest_comment_dt = comments[-1]["_parsed_dt"]
        last_published_at_str = latest_comment_dt.strftime(OUTPUT_DATETIME_FORMAT)
        last_pub_dt_for_filename = latest_comment_dt.strftime(FILE_DATETIME_FORMAT)

        # JSON出力から内部管理用フィールドを破棄
        for c in comments:
            del c["_parsed_dt"]

    # 保存ファイルの命名設定
    if last_pub_dt_for_filename:
        filename = f"comments_{video_id}_{last_pub_dt_for_filename}.json"
    else:
        filename = f"comments_{video_id}_null.json"

    # 出力用辞書の作成
    output_data = {
        "commentList": comments,
        "executedAt": executed_at_str,
        "lastPublishedAt": last_published_at_str
    }

    # JSONファイルへ書き出し
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=4)

    # 実行結果の計算とコンソール出力
    end_time = time.time()
    elapsed_time = end_time - start_time

    print("\n--- 実行結果 ---")
    print(f"1. 取得コメント数: {len(comments)} 件")
    print(f"2. プログラム終了日時 (UTC): {executed_at_str}")
    print(f"3. 実行時間: {elapsed_time:.2f} 秒")
    print(f"保存ファイル: {filename}\n")

if __name__ == "__main__":
    main()