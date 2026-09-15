# tweets

近況つぶやきを旧Twitter風のUIで公開する静的サイト。

## 更新方法(Macから)

1. `tweet.txt` の末尾に、空行区切りで新しいつぶやきを追記する。
2. 以下を実行する(HTML再生成 + commit + push を一括で行う)。

   ```bash
   ./post.sh
   ```

   または `つぶやきを投稿.command` をダブルクリックする。

## 更新方法(スマホから)

1. スマホのブラウザ、またはGitHubアプリで
   https://github.com/keisato0/tweets/edit/main/tweet.txt を開く。
2. 末尾に空行を1行はさんで新しいつぶやきを追記する。
3. そのまま「Commit changes」で `main` ブランチに直接コミットする。

コミットすると GitHub Actions (`.github/workflows/build.yml`) が自動で
`generate.py` を実行し、生成されたサイトを再度コミット・pushしてくれる
(数十秒〜1分程度)。Mac側での操作は不要。

新しく追加されたつぶやきには、生成スクリプトを実行した時刻が投稿日時として
割り当てられ、`state.json` に記録される(以後の実行で上書きされない)。
1回の実行で複数のつぶやきを追加した場合は、それらすべてに同じ投稿日時が
付与される。

最新100件は `index.html` に、それより古いものは100件単位で
`archive/page2.html`, `archive/page3.html`, ... に分割される。
