# index.html(社内レビュー用) から WordPress 用テンプレートを作るスクリプト。
# ザ・セールLP(page-lp-sale2026.php)と同じ構成にする。
#   使い方: python build_wp.py
#   出力:   wp-deploy/page-lp-shitadori2026.php
#           wp-deploy/lp/assets/shitadori2026/img/ (使っている画像だけコピー)
# index.html を直したら、このスクリプトを実行し直せば WordPress 版にも反映される。
import hashlib
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).parent
SLUG = 'shitadori2026'
OUT_PHP = ROOT / 'wp-deploy' / f'page-lp-{SLUG}.php'
OUT_IMG = ROOT / 'wp-deploy' / 'lp' / 'assets' / SLUG / 'img'


def replace_once(s, old, new):
    if s.count(old) != 1:
        raise SystemExit(f'置き換え箇所が見つからない(または複数ある): {old[:60]!r}')
    return s.replace(old, new)


s = (ROOT / 'index.html').read_text(encoding='utf-8')

# 1. 社内レビュー用パスワードゲートを削除(本番では不要)
s = re.sub(r'\n  <div id="preview-gate".*?</script>\n', '\n', s, count=1, flags=re.S)
s = replace_once(s, '<body class="preview-locked">',
                 "<body>\n  <?php include get_stylesheet_directory() . '/lp/lp-tracking-body.php'; ?>")

# 2. GA4の直接タグを外し、共通の計測ファイル(GTM)に置き換える
s, n = re.subn(r'<!-- Google tag \(gtag\.js\).*?</script>\n', '', s, count=1, flags=re.S)
if n != 1:
    raise SystemExit('GA4タグのブロックが見つからない')
s = re.sub(r'(<title>.*?</title>\n)',
           r"\1<?php include get_stylesheet_directory() . '/lp/lp-tracking-head.php'; ?>\n", s, count=1)

# 3. クリック計測は GTM が拾える dataLayer.push({event: ...}) の形で送る
s = replace_once(s, "  function track(name, params){ gtag('event', name, params); }",
                 "  function track(name, params){\n"
                 "    window.dataLayer = window.dataLayer || [];\n"
                 "    var d = { event: name };\n"
                 "    for (var k in params) d[k] = params[k];\n"
                 "    window.dataLayer.push(d);\n"
                 "  }")
s = replace_once(s, '// クリック計測(GA4イベント)。GA4を読み込んでいない環境(社内レビュー等)では dataLayer に積まれるだけで送信されない',
                 '// クリック計測。dataLayer にカスタムイベントとして送る(GA4へ送るにはGTM側でトリガーとタグの設定が必要)')

# 4. OGPのURLを本番用に
s = s.replace('<!-- SNS・LINEでシェアされた時の表示。本番URLに移したら og:url / og:image のURLも差し替えること -->', '<!-- SNS・LINEでシェアされた時の表示 -->')
s = re.sub(r'<meta property="og:url" content="[^"]*">',
           '<meta property="og:url" content="<?php echo esc_url( get_permalink() ); ?>">', s)
s = re.sub(r'<meta property="og:image" content="[^"]*">',
           '<meta property="og:image" content="<?php echo $lp_assets; ?>/ogp.png">', s)

# 5. 画像のパスを差し替え、使っている画像だけコピー(?v= はファイル内容から作るので差し替え時に自動で変わる)
OUT_IMG.mkdir(parents=True, exist_ok=True)
used = sorted(set(re.findall(r'src="img/([^"]+)"', s)))
for name in used:
    src = ROOT / 'img' / name
    ver = hashlib.md5(src.read_bytes()).hexdigest()[:8]
    shutil.copy2(src, OUT_IMG / name)
    s = s.replace(f'src="img/{name}"', f'src="<?php echo $lp_assets; ?>/{name}?v={ver}"')
shutil.copy2(ROOT / 'img' / 'ogp.png', OUT_IMG / 'ogp.png')

if 'src="img/' in s or 'gtag(' in s or 'preview-gate"' in s:
    raise SystemExit('変換漏れがある')

header = ("<?php\n"
          f"/* page-lp-{SLUG}.php : アイメガネ メガネの無料相談＆下取りキャンペーン LP\n"
          "   ※ このファイルは build_wp.py で index.html から自動生成。直接編集せず index.html を直して再生成すること */\n"
          f"$lp_assets = get_stylesheet_directory_uri() . '/lp/assets/{SLUG}/img';\n"
          "?>\n")
OUT_PHP.write_text(header + s, encoding='utf-8', newline='\n')
print(f'出力: {OUT_PHP.relative_to(ROOT)}')
print(f'画像: {len(used) + 1}ファイル → {OUT_IMG.relative_to(ROOT)}')
