"""Build a local review page from real run records and a verification manifest."""

import argparse
import html
import json
import uuid
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'runtime-local/verification/auto-quality-20261011'


def build(manifest_path: Path) -> Path:
    """Create gallery and measured summary; never generate or alter cut ranges."""
    manifest = json.loads(manifest_path.read_text())
    groups: Dict[str, List[str]] = {'comparison': [], 'new': []}
    summary = []
    for item in manifest['samples']:
        run_id = str(uuid.UUID(item['run_id']))
        record = json.loads((ROOT / 'runtime-local/runs' / run_id / 'run.json').read_text())
        v = record['output']['validation']
        tokens = sum(c.get('usage', {}).get('total_tokens', 0) for c in record['calls'] if c.get('usage'))
        clips = len(record['timeline']['tracks']['video'])
        speech = len([s for s in record['timeline']['tracks']['subtitles'] if s.get('kind') == 'speech'])
        title_count = len([s for s in record['timeline']['tracks']['subtitles'] if s.get('kind') == 'title'])
        data = {**item, 'status': record['status'], 'validation': v, 'tokens': tokens,
                'clip_count': clips, 'title_count': title_count, 'speech_count': speech,
                'call_count': len(record['calls']), 'output_path': record['output']['output_path']}
        summary.append(data)
        notes = ''.join(f'<li>{html.escape(note)}</li>' for note in item.get('notes', []))
        groups[item['group']].append(f'''<article><div class="badge">{html.escape(item['kind'])}</div>
<h3>{html.escape(item['label'])}</h3><div class="meta">{v['duration_s']:.2f}秒 · {clips}个选段 · {title_count}处标题 · {v['width']}×{v['height']}</div>
<video controls playsinline preload="metadata" poster="/api/runs/{run_id}/preview" src="/api/runs/{run_id}/video"></video>
<ul>{notes}</ul><div class="links"><a href="/?run={run_id}">打开与修改</a><a href="/api/runs/{run_id}/video" download>下载视频</a><a href="/api/runs/{run_id}/record" download>运行记录</a></div>
<details><summary>查看本次记录</summary><p>状态：{record['status']}；完整解码：{'通过' if v['decoded'] else '未通过'}；语音字幕：{speech}条；模型请求：{len(record['calls'])}次；返回token总量：{tokens}。实际账单金额未知。</p><p>运行编号：{run_id}</p></details></article>''')
    failures = ''.join(f'<li>{html.escape(i["label"])}：<a href="/api/runs/{str(uuid.UUID(i["run_id"]))}/record">查看失败记录</a></li>'
                       for i in manifest.get('failures', []))
    page = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AutoCut · 自动剪辑样片对照</title>
<style>*{box-sizing:border-box}body{margin:0;background:#f5f7f2;color:#163532;font:15px/1.65 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}main{max-width:1150px;margin:auto;padding:30px 25px 60px}h1{font-size:34px;line-height:1.2}h2{margin:36px 0 18px}h3{font-size:19px;margin:8px 0}.intro,.meta,details{color:#657a76}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px}article{background:white;border:1px solid #dbe5df;border-radius:18px;padding:18px}video{width:100%;height:290px;background:#172e29;object-fit:contain;border-radius:10px;margin:15px 0}ul{padding-left:18px;font-size:13px}a{color:#176b58}.links{display:flex;gap:10px;flex-wrap:wrap;font-size:13px}.badge{display:inline-block;border-radius:20px;padding:3px 10px;background:#eef5ef;color:#176b58;font-size:12px}details{font-size:12px;margin-top:15px;overflow-wrap:anywhere}.note{border-left:3px solid #dcaa51;background:#fff9ed;padding:14px;margin:20px 0;font-size:13px}footer{margin-top:25px;font-size:13px}@media(max-width:850px){.grid{grid-template-columns:1fr}video{height:320px}h1{font-size:28px}}</style>
<main><a href="/">← 继续剪辑</a><h1>自动选片，实际看效果。</h1><p class="intro">2026年10月11日 · 拉面对照 ＋ 三组新素材。新样片由系统选择切点，保留原声。</p>
<div class="note">自动导出通过，不代表剪辑质量已经合格。请观看动作和切点、听原声，并核对语音字幕。餐厅转录仍有错字；模型复核意见也可能出错。这些是产品开发样片，尚未完成盲评。</div>
<h2>01 / 拉面：人工参考与自动方案</h2><div class="grid">''' + ''.join(groups['comparison']) + '''</div>
<h2>02 / 从零生成的新样片</h2><div class="grid">''' + ''.join(groups['new']) + '''</div>
<footer><details><summary>保留的问题与失败记录</summary><ul>''' + failures + '''</ul><p>自动复核中间版与所有原始响应均在本地保留；没有用人工切点覆盖自动结果。输入选择和剪辑要求由助手给定，具体区间由系统选取；这些素材尚不是冻结的研究测试集。</p></details></footer></main></html>'''
    DEST.mkdir(parents=True, exist_ok=True)
    (DEST / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    target = DEST / 'gallery.html'
    target.write_text(page)
    return target


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('manifest', type=Path)
    args = parser.parse_args()
    print(build(args.manifest))
