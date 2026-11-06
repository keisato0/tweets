// Tweet.app の中身。ローカルの投稿サーバー(compose_server.py)を立ち上げて、
// ブラウザで投稿画面を開く。Shift を押しながら起動したときだけ、既存の
// ウィンドウにタブを足すのではなく、新しいウィンドウで開く。
//
// 直したら ./build_tweet_app.sh を実行して Tweet.app を作り直すこと。
//
// AppleScript のアプレットから作り替えたのは、起動が速いため。アプレットは
// スクリプトの1行目に届くまで約0.4秒かかり、その間に Shift を離されると
// 判定を取り逃がす。Swift なら 0.07 秒前後で読める。

import AppKit
import Foundation

let siteURL = "http://localhost:8765/"
let logPath = "/tmp/tweets_compose_server.log"

// サーバーの起動で時間が経つ前に、まずキーの状態を読む
let wantsNewWindow = NSEvent.modifierFlags.contains(.shift)

// Tweet.app はリポジトリの直下に置いてある。アプリの位置から辿ることで、
// リポジトリごと移動しても動くようにする。
func projectDirectory() -> String {
    let beside = Bundle.main.bundleURL.deletingLastPathComponent()
    if FileManager.default.fileExists(atPath:
        beside.appendingPathComponent("compose_server.py").path) {
        return beside.path
    }
    return "/Users/kei/homepages/tweets"
}

@discardableResult
func run(_ path: String, _ args: [String]) -> Int32 {
    let p = Process()
    p.executableURL = URL(fileURLWithPath: path)
    p.arguments = args
    do { try p.run() } catch { return -1 }
    p.waitUntilExit()
    return p.terminationStatus
}

let dir = projectDirectory()
run("/bin/sh", ["-c",
    "cd \(dir) && (python3 compose_server.py > \(logPath) 2>&1 &) ; sleep 1"])

if wantsNewWindow {
    // ブラウザ名を直接書いているのは、「新規ウィンドウを作る」がブラウザごとの
    // 用語で、アプリ名が決まっていないと解釈できないため
    let script = """
        tell application "Brave Browser"
            activate
            make new window
            set URL of active tab of front window to "\(siteURL)"
        end tell
        """
    if run("/usr/bin/osascript", ["-e", script]) != 0 {
        // 操作できなかったときは、いつもどおり既定のブラウザに任せる
        run("/usr/bin/open", [siteURL])
    }
} else {
    run("/usr/bin/open", [siteURL])
}
