# tweets

近況つぶやきを旧Twitter風のUIで公開する静的サイト。

## 更新方法(Macから)

以下の2通りの方法がある。

**A. tweets.txt を直接編集する場合(旧来の方法)**

1. `tweets.txt` の末尾に、空行区切りで新しいつぶやきを追記する。
2. 以下を実行する(HTML再生成 + commit + push を一括で行う)。

   ```bash
   ./post.sh
   ```

   または `つぶやきを投稿.command` をダブルクリックする。

**B. ブラウザのフォームから投稿する場合**

1. `ツイートを書く(ブラウザ版).app` をダブルクリックする(ターミナルは開かない)。
2. ブラウザが自動で開き、投稿フォームが表示される。
3. テキストエリアに書いて「投稿」を押す(`tweets.txt` への追記 +
   HTML再生成 + commit + push まで自動で行われる)。投稿後もそのまま続けて
   次のツイートを書ける。しばらく操作がないとローカルのサーバーは自動終了する
   (タブはそのまま閉じてよい)。裏側は `compose_server.py` が
   `http://localhost:8765/` で動いている。

## 更新方法(スマホから)

**A. PWA投稿フォームを使う場合(推奨)**

1. スマホのブラウザで https://keisato0.github.io/tweets/post.html を開く
   (あらかじめホーム画面に追加しておくとアプリのように起動できる)。
2. 初回のみ、GitHubのアクセストークンを求められるので入力する。
   github.com の Settings > Developer settings > Personal access tokens >
   Fine-grained tokens で、リポジトリを `keisato0/tweets` のみに限定し、
   Permissions の `Contents: Read and write` だけを許可したトークンを
   発行して貼り付ける(トークンは端末のブラウザにのみ保存される)。
3. テキストエリアに書いて「投稿」を押すと、GitHub API経由で `tweets.txt`
   に直接追記・コミットされる(コミットメッセージは
   `つぶやきを追加(スマホPWA)`)。投稿後もそのまま続けて次のツイートを書ける。

**B. GitHubの編集画面を直接使う場合**

1. スマホのブラウザ、またはGitHubアプリで
   https://github.com/keisato0/tweets/edit/main/tweets.txt を開く。
2. 末尾に空行を1行はさんで新しいつぶやきを追記する。
3. そのまま「Commit changes」で `main` ブランチに直接コミットする。

いずれの方法でコミットしても GitHub Actions (`.github/workflows/build.yml`)
が自動で `generate.py` を実行し、生成されたサイトを再度コミット・push
してくれる(数十秒〜1分程度)。Mac側での操作は不要。

新しく追加されたつぶやきには、生成スクリプトを実行した時刻が投稿日時として
割り当てられ、`state.json` に記録される(以後の実行で上書きされない)。
1回の実行で複数のつぶやきを追加した場合は、それらすべてに同じ投稿日時が
付与される。

最新100件は `index.html` に、それより古いものは100件単位で
`archive/page2.html`, `archive/page3.html`, ... に分割される。
