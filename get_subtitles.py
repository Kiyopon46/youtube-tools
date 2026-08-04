import sys
import re
import os
from youtube_transcript_api import YouTubeTranscriptApi

def validate_input(video_id, lang):
    """
    セキュリティ対策 (1): 入力値の検証とサニタイズ
    """
    video_id_pattern = r'^[a-zA-Z0-9_-]{11}$'
    lang_pattern = r'^[a-z]{2,3}(-[A-Z]{1,4})?$'

    if not re.match(video_id_pattern, video_id):
        sys.exit("エラー: 無効な動画IDフォーマットです。(半角英数字・ハイフン・アンダースコア11桁)")

    if not re.match(lang_pattern, lang):
        sys.exit("エラー: 無効な言語コードフォーマットです。(例: ja, en, ko)")

def get_subtitles(video_id, languages=['ja', 'en', 'ko']):
    try:
        # youtube-transcript-api v1.2.4 対応
        ytt = YouTubeTranscriptApi()
        fetched_transcript = ytt.fetch(video_id, languages=languages)
        
        # snippets からテキストを抽出
        full_text = "\n".join([snippet.text for snippet in fetched_transcript.snippets])
        return full_text

    except Exception as e:
        print(f"字幕の取得中にエラーが発生しました: {e}", file=sys.stderr)
        return None

def main():
    if len(sys.argv) != 3:
        sys.exit("使い方: python get_subtitles.py <動画ID> <言語[ja,en,ko]>")

    video_id = sys.argv[1]
    lang = sys.argv[2]
    
    # 入力値の安全性チェック
    validate_input(video_id, lang)

    # 字幕の取得
    subtitles = get_subtitles(video_id, [lang])

    print(f"--- 字幕テキスト ({lang}) ---")

    if subtitles is None:
        print("指定された言語の字幕を取得できなかったため、ファイルを保存せずに終了します。")
        sys.exit(1)

    print(subtitles)

    # 安全なファイル名の生成
    filename = f"{video_id}_{lang}.txt"
    file_path = os.path.abspath(filename)

    try:
        with open(file_path, "w", encoding="utf-8", newline="") as f:
            f.write(subtitles)
        print(f"\nファイルに保存しました: {file_path}")

    except Exception as e:
        sys.exit(f"エラー: 歌詞ファイルの書き出しに失敗しました: {e}")

if __name__ == "__main__":
    main()