# tweets

近況つぶやきを旧Twitter風のUIで公開する静的サイト。

## 更新方法

1. `tweet.txt` の末尾に、空行区切りで新しいつぶやきを追記する。
2. 以下を実行してHTMLを再生成する。

   ```bash
   python3 generate.py
   ```

3. 変更を commit / push する。

   ```bash
   git add -A
   git commit -m "つぶやきを追加"
   git push
   ```

新しく追加されたつぶやきには、生成スクリプトを実行した時刻が投稿日時として
割り当てられ、`state.json` に記録される(以後の実行で上書きされない)。
1回の実行で複数のつぶやきを追加した場合は、それらすべてに同じ投稿日時が
付与される。

最新100件は `index.html` に、それより古いものは100件単位で
`archive/page2.html`, `archive/page3.html`, ... に分割される。
