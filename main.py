import os
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv
import openai

import sqlalchemy
import sqlalchemy.ext.declarative
import sqlalchemy.orm
import datetime

# 環境変数を読み込む
load_dotenv()
openai.api_key=os.environ.get("OPENAI_API_KEY")
# ボットトークンとソケットモードハンドラーを使ってアプリを初期化します
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))
model_name = "text-davinci-003"

### パラメータを指定して使いまわす関数を定義
def davinciStrictive(prompt):
    completions = openai.Completion.create(
        prompt = prompt.replace("\n", " "),
        engine = model_name,
        max_tokens = 2048,
        temperature = 0.12,
        n = 1, stop = None
    )
    text = completions.choices[0].text
    return text

# エンジンの定義
engine = sqlalchemy.create_engine('sqlite:///database.db', echo=True)

# sqlalchemyでデータベースのテーブルを扱うための宣言
Base = sqlalchemy.ext.declarative.declarative_base()

# テーブルのフィールドを定義
class Session(Base):
    __tablename__ = 'sessions'
    id = sqlalchemy.Column(
        sqlalchemy.Integer, primary_key=True, autoincrement=True
    )
    prompt = sqlalchemy.Column(sqlalchemy.String(500))
    completion = sqlalchemy.Column(sqlalchemy.String(500))
    channel_id = sqlalchemy.Column(sqlalchemy.String(100))
    created_at = sqlalchemy.Column(sqlalchemy.DateTime)

# データベースにテーブルを作成
Base.metadata.create_all(engine)

# データベースに接続するためのセッションを準備
SessionDataBase = sqlalchemy.orm.sessionmaker(bind=engine)

class SessionManager:
    def __init__(self):
        self.session = SessionDataBase()

    def add_record(self, prompt, completion, channel_id):
        # レコードを準備し、セッションを通してデータベースに送る
        s = Session(
            prompt=prompt,
            completion=completion,
            channel_id=channel_id,
            created_at=datetime.datetime.now()
        )
        self.session.add(s)
        self.session.commit()

    def get_pair_list(self, channel_id):
        # channel_idを指定して、promptとcompletionを古い順に取得する
        record_list = self.session.query(Session).filter_by(channel_id=channel_id).order_by(Session.created_at.asc()).all()
        # promptとcompletionのペアの配列を取得する
        pair_list = [(record.prompt, record.completion) for record in record_list]
        return pair_list

    def delete_pair_list(self, channel_id):
        # データベースから指定されたchannel_idのレコードを削除する
        record_list = self.session.query(Session).filter_by(channel_id=channel_id).all()
        for record in record_list:
            self.session.delete(record)
        self.session.commit()

    def get_pair_count(self, channel_id):
        # データベースから指定されたchannel_idのレコードの件数を取得する
        count = self.session.query(Session).filter_by(channel_id=channel_id).count()
        return count

sm = SessionManager()

@app.event("app_mention")
def message_mention(say, event):
    input_prompt = event["text"].replace("<@"+os.environ.get("SLACK_BOT_ID")+">", "").strip()   
    template = ""
    for prompt, completion in sm.get_pair_list(event["channel"]):
        template += "User:"+prompt.replace("\n", " ") + "\n"
        template += "Assistant:"+completion.replace("\n", "") + "\n"
    prompt = template + "User: " + input_prompt.replace("\n", "") + "\n" + "Assistant: "
    print(prompt)
    completion = davinciStrictive(prompt)
    sm.add_record(input_prompt, completion, event["channel"])
    say(completion)

@app.command("/gpt-cmd")
def greet_command(ack, say, respond, command):
    # スラッシュコマンドを受け取ったことを通知
    ack()

    # 引数を取得
    cmd = command["text"]
    # ユーザーIDを取得
    user_id = command["user_id"]
    # チャンネルIDを取得
    channel_id = command["channel_id"]

    # 引数を使用してメッセージを送信
    help_text = """
    スラッシュコマンドの後に文字列を入れると、以下のことができます
```
- history 会話の文脈を表示
- forget  このチャンネル上での会話の文脈をリセット
```
"""
    if cmd == "history":
        history = ""
        for pair in sm.get_pair_list(channel_id):
            history += f"<@{user_id}>:" + pair[0]+ "\nAI:" + pair[1] + "\n"
        respond(history)
        say("今までの会話の数は「" + str(sm.get_pair_count(channel_id))+"」")
    elif cmd == "forget":
        sm.delete_pair_list(channel_id)
        say("このチャンネル上の会話をすべてリセットしました")
    else:
        respond(help_text)

    
    # respond(f"{cmd}, <@{user_id}> in {channel_id}!")

# アプリを起動します
if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
